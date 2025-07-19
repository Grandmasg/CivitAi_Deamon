import unittest
import json
from daemon import process_manifest, make_queue_item

class DummyDaemon:
    def __init__(self):
        self.jobs = []
    def add_job(self, item):
        self.jobs.append(item)

class TestManifestParsing(unittest.TestCase):
    def test_manifest_parsing(self):
        manifest = [
            {"modelId": "1", "url": "url1", "filename": "f1", "sha256": "sha1", "priority": 1},
            {"modelId": "2", "url": "url2", "filename": "f2"}
        ]
        with open('test_manifest.json', 'w') as f:
            json.dump(manifest, f)
        daemon = DummyDaemon()
        process_manifest('test_manifest.json', daemon)
        self.assertEqual(len(daemon.jobs), 2)
        self.assertEqual(daemon.jobs[0]['model_id'], '1')
        self.assertEqual(daemon.jobs[1]['filename'], 'f2')

    def test_manifest_validation(self):
        # Fout pad: ontbrekende velden
        manifest = [{"modelId": "1"}]
        with open('test_manifest_invalid.json', 'w') as f:
            json.dump(manifest, f)
        daemon = DummyDaemon()
        process_manifest('test_manifest_invalid.json', daemon)
        self.assertEqual(daemon.jobs[0]['url'], None)

if __name__ == '__main__':
    unittest.main()
