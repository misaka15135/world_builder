"""Regression tests for active/archive work-order integrity."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'tools/check_project_docs.py'
spec = importlib.util.spec_from_file_location('project_docs_check', MODULE)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class WorkOrderRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'work_order'
        self.archive = self.work / 'archive/legacy'
        self.archive.mkdir(parents=True)
        self.master = self.work / '000_plan.md'
        self.task = self.work / '002_task.md'
        self.master.write_text('# Plan\n- 状态：in_progress\n- 依赖：无\n', encoding='utf-8')
        self.task.write_text('# Task\n- 状态：planned\n- 依赖：000\n', encoding='utf-8')
        self.old = self.archive / '001_old.md'
        self.old.write_text('# Old\n- 状态：planned\n- [ ] unfinished\n', encoding='utf-8')
        (self.work / 'README.md').write_text('[Plan](000_plan.md)\n[Task](002_task.md)\n', encoding='utf-8')
        (self.work / 'BACKLOG.md').write_text('## B01 Future\n', encoding='utf-8')
        self.registry = {'version':1, 'active':['000','002'], 'backlog':['B01'], 'snapshots':[],
                         'archived':[{'id':'001','path':'work_order/archive/legacy/001_old.md',
                                      'status_at_archive':'planned','disposition':'transferred',
                                      'successors':['002','B01'],
                                      'archive_sha256':hashlib.sha256(self.old.read_bytes()).hexdigest()}]}
        self.save()

    def save(self):
        (self.work / 'registry.json').write_text(json.dumps(self.registry), encoding='utf-8')

    def errors(self):
        return checker.check_work_orders(self.root)

    def test_valid_archive_does_not_require_historical_work_to_be_done(self):
        self.assertEqual(self.errors(), [])

    def test_changed_historical_content_is_rejected(self):
        self.old.write_text(self.old.read_text(encoding='utf-8') + 'edited\n', encoding='utf-8')
        self.assertTrue(any('hash mismatch' in e for e in self.errors()))

    def test_unmapped_unfinished_work_is_rejected(self):
        self.registry['archived'][0]['successors'] = []
        self.save()
        self.assertTrue(any('unmapped' in e for e in self.errors()))

    def test_unknown_successor_is_rejected(self):
        self.registry['archived'][0]['successors'] = ['B99']
        self.save()
        self.assertTrue(any('unknown successor' in e for e in self.errors()))

    def test_active_dependency_cycle_is_rejected(self):
        self.master.write_text('# Plan\n- 状态：in_progress\n- 依赖：002\n', encoding='utf-8')
        self.assertTrue(any('cycle' in e for e in self.errors()))

    def test_archived_dependency_cannot_reenter_active_schedule(self):
        self.task.write_text('# Task\n- 状态：planned\n- 依赖：001\n', encoding='utf-8')
        self.assertTrue(any('inactive/unknown dependency' in e for e in self.errors()))

    def test_reused_id_is_rejected(self):
        self.registry['active'].append('001')
        self.save()
        self.assertTrue(any('duplicate' in e for e in self.errors()))

    def test_missing_archive_is_rejected(self):
        self.old.unlink()
        self.assertTrue(any('missing archived' in e for e in self.errors()))

    def test_done_order_cannot_retain_unfinished_items(self):
        self.task.write_text('# Task\n- 状态：done\n- 依赖：000\n- [ ] incomplete\n', encoding='utf-8')
        self.assertTrue(any('pending item' in e for e in self.errors()))

    def test_archived_snapshot_tampering_is_rejected(self):
        snapshot = self.archive / 'README.md'
        snapshot.write_text('original', encoding='utf-8')
        self.registry['snapshots'] = [{'path':'work_order/archive/legacy/README.md',
                                      'sha256':hashlib.sha256(snapshot.read_bytes()).hexdigest()}]
        self.save()
        snapshot.write_text('changed', encoding='utf-8')
        self.assertTrue(any('snapshot changed' in e for e in self.errors()))


if __name__ == '__main__':
    unittest.main()
