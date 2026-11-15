#!/usr/bin/env python3
"""Exercise SQL design constraints in an isolated in-memory database."""
import json, sqlite3
from pathlib import Path
schema=Path(__file__).resolve().parents[1] / 'contracts/repository-extension.design.sql'
c=sqlite3.connect(':memory:',isolation_level=None)
c.executescript(schema.read_text())
checks=[]
c.execute("INSERT INTO connection_probes VALUES('probe1','conn1','cfg','native_tools','succeeded',3,1,4096,100,'exact','probe-result','2026-11-12T00:00:00Z')")
checks.append('successful_probe_without_world_revision')
def reject(name,sql,args=()):
 c.execute('SAVEPOINT negative')
 try:
  c.execute(sql,args)
 except sqlite3.IntegrityError:
  c.execute('ROLLBACK TO negative');c.execute('RELEASE negative');checks.append(name);return
 c.execute('ROLLBACK TO negative');c.execute('RELEASE negative');raise AssertionError(name+' was accepted')
reject('successful_probe_requires_result',"UPDATE connection_probes SET result_ref=NULL WHERE probe_id='probe1'")
def world(w,r):
 c.execute('BEGIN IMMEDIATE')
 c.execute('INSERT INTO worlds(world_id,name,created_at) VALUES(?,?,?)',(w,w,'2026-11-12T00:00:00Z'))
 c.execute('INSERT INTO revisions(revision_id,world_id,snapshot_hash,created_at) VALUES(?,?,?,?)',(r,w,'sha256:empty','2026-11-12T00:00:00Z'))
 c.execute('UPDATE worlds SET head_revision_id=?,head_generation=1 WHERE world_id=?',(r,w));c.execute('COMMIT')
world('w1','r0');world('w2','r2')
def op(o,w,r,k):
 c.execute('INSERT INTO operations(operation_id,world_id,base_revision_id,expected_head_generation,actor_id,command_kind,idempotency_key,request_hash,state,deadline_at,created_at) VALUES(?,?,?,1,?,?,?,?,?,?,?)',(o,w,r,'user','create',k,'hash','running','2026-11-12T01:00:00Z','2026-11-12T00:00:00Z'))
op('op1','w1','r0','k1');op('op2','w2','r2','k2')
for o,t in [('op1','t1'),('op1','t2'),('op2','other')]:
 c.execute('INSERT INTO task_versions(task_id,task_version,operation_id,graph_version,capability,definition_hash,definition_json,scope_json,state) VALUES(?,1,?,1,?,?,?,?,?)',(t,o,'build','hash','{}','{}','ready'))
c.execute("INSERT INTO candidates VALUES('cand1','op1','w1','r0',1,0,0,'patch',NULL,'draft',0,NULL,'2026-11-12T00:00:00Z')")
for t in ['t1','t2']: c.execute("INSERT INTO candidate_tasks VALUES('op1','cand1',?,1,'artifact')",(t,))
assert c.execute('SELECT COUNT(*) FROM candidate_tasks').fetchone()[0]==2;checks.append('candidate_multi_task_aggregation')
reject('cross_operation_candidate_task',"INSERT INTO candidate_tasks VALUES('op1','cand1','other',1,'artifact')")
reject('cross_world_base',"UPDATE operations SET base_revision_id='r2' WHERE operation_id='op1'")
reject('stale_generation',"UPDATE worlds SET head_revision_id='r0',head_generation=0 WHERE world_id='w1'")
reject('immutable_revision',"UPDATE revisions SET snapshot_hash='mutated' WHERE revision_id='r0'")
reject('unvalidated_candidate_accept',"UPDATE candidates SET state='accepted',accepted_revision_id='r0' WHERE candidate_id='cand1'")
reject('invalid_task_state',"UPDATE task_versions SET state='done' WHERE task_id='t1'")
reject('immutable_task_definition',"UPDATE task_versions SET definition_json='changed' WHERE task_id='t1'")
c.execute("INSERT INTO tool_calls VALUES('call1','op1','t1',1,'call-key','tool','draft','args','unknown',1,1,0,NULL,NULL,'2026-11-12T00:00:00Z')")
reject('duplicate_call_idempotency',"INSERT INTO tool_calls VALUES('call2','op1','t1',1,'call-key','tool','draft','args','queued',0,1,0,NULL,NULL,'2026-11-12T00:00:00Z')")
reject('success_requires_receipt',"UPDATE tool_calls SET state='succeeded' WHERE call_id='call1'")
c.execute("INSERT INTO budget_accounts(operation_id,dimension,limit_units) VALUES('op1','tokens',100)")
c.execute("INSERT INTO budget_reservations VALUES('b1','op1','tokens','call1','unknown',80,80,0,NULL,0)")
assert c.execute('SELECT reserved_units FROM budget_accounts').fetchone()[0]==80;checks.append('unknown_budget_stays_reserved')
reject('over_budget_reservation',"INSERT INTO budget_reservations VALUES('b2','op1','tokens','call2','held',30,30,0,NULL,0)")
c.execute("UPDATE budget_reservations SET state='settled',held_units=0,settled_units=80,observed_units=150,overrun_units=70 WHERE reservation_id='b1'")
assert c.execute('SELECT reserved_units,settled_units,overrun_units FROM budget_accounts').fetchone()==(0,80,70);checks.append('observed_overrun_preserved')
c.execute("INSERT INTO events VALUES('e1','op1',1,NULL,NULL,'operation.created','2026-11-12T00:00:00Z','created',NULL)")
reject('duplicate_event_cursor',"INSERT INTO events VALUES('e2','op1',1,NULL,NULL,'operation.created','2026-11-12T00:00:00Z','created',NULL)")
reject('invalid_spatial_bounds',"INSERT INTO spatial_reads VALUES('s1','cand1','{}',5,1,0,1,0,1,'empty',0)")
reject('invalid_field_lock',"INSERT INTO locks VALUES('l1','w1','user','field',NULL,'/material',NULL,1)")
assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
assert c.execute('PRAGMA integrity_check').fetchone()==('ok',)
print(json.dumps({'scope':'SQL design illustration in isolated in-memory SQLite; not a product migration or runtime test','sqlite_version':sqlite3.sqlite_version,'tables':c.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0],'checks':checks,'errors':[]},ensure_ascii=False,indent=2))
