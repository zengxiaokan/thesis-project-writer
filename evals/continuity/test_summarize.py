import json
from pathlib import Path
import runpy
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SUMMARY = runpy.run_path(str(HERE / 'summarize.py'))
READ = runpy.run_path(str(HERE / 'material_reader.py'))['read_material']


class LoggedEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='thesis-logged-evidence-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        (self.project / 'a.py').write_bytes(b'A = 1\n')
        (self.project / 'b.py').write_bytes(b'B = 2\n')
        self.materials = {'a.py': b'A = 1\n', 'b.py': b'B = 2\n'}
        self.log = self.root / 'read.jsonl'

    def test_disk_hashes_are_not_counted_as_model_content_events(self):
        READ(self.project, self.log, inventory=True)
        READ(self.project, self.log, paths=['a.py'])
        READ(self.project, self.log, paths=['a.py'])
        observed = SUMMARY['logged_reads'](self.log, self.materials)
        self.assertEqual(observed['hash_disk_reads'], 2)
        self.assertEqual(observed['hash_disk_bytes'], 12)
        self.assertEqual(observed['unique_content_files'], 1)
        self.assertEqual(observed['repeated_content_events'], 1)

    def test_wrong_source_fingerprint_is_not_accepted_as_read_evidence(self):
        READ(self.project, self.log, inventory=True)
        READ(self.project, self.log, paths=['a.py'])
        events = [json.loads(line) for line in self.log.read_text(encoding='utf-8').splitlines()]
        events[1]['files'][0]['sha256_text_lf'] = '0' * 64
        self.log.write_text('\n'.join(json.dumps(item) for item in events), encoding='utf-8')
        with self.assertRaises(ValueError):
            SUMMARY['logged_reads'](self.log, self.materials)

    def test_content_log_without_inventory_is_explicitly_incomplete(self):
        READ(self.project, self.log, paths=['a.py'])
        with self.assertRaises(ValueError):
            SUMMARY['logged_reads'](self.log, self.materials)

    def test_version_change_keeps_background_selector_unchanged(self):
        first, second = SUMMARY['material_versions']()
        self.assertEqual(len([name for name in first if name.startswith('modules/')]), 20)
        self.assertEqual(len([name for name in second if name.startswith('modules/')]), 21)
        changed = {name for name in first.keys() | second.keys()
                   if name not in first or name not in second
                   or SUMMARY['fingerprint'](first[name]) != SUMMARY['fingerprint'](second[name])}
        self.assertEqual(changed, {'registry.py', 'modules/orders/service.py', 'modules/recalls/service.py'})
        self.assertEqual(first['modules/recovery/service.py'], second['modules/recovery/service.py'])
