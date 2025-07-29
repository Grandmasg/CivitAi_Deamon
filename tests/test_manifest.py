import unittest
import json
from backend.daemon import process_manifest, make_queue_item
from loguru import logger
import os

# Loguru test log setup
_test_log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(_test_log_dir, exist_ok=True)
logger.add(os.path.join(_test_log_dir, "test.log"), rotation="1 MB", retention=3, encoding="utf-8")

class DummyDaemon:
    def __init__(self):
        self.jobs = []
    def add_job(self, item):
        self.jobs.append(item)

class TestManifestParsing(unittest.TestCase):
    def test_manifest_parsing(self):
        manifest = [
            {"modelId": "1", "modelVersionId": "101", "url": "url1", "filename": "f1", "sha256": "sha1", "priority": 1, "model_type": "checkpoint", "baseModel": "SD15"},
            {"modelId": "2", "modelVersionId": "202", "url": "url2", "filename": "f2", "model_type": "vae", "baseModel": "SDXL"}
        ]
        with open('configs/test_manifest.json', 'w') as f:
            json.dump(manifest, f)
        daemon = DummyDaemon()
        process_manifest('configs/test_manifest.json', daemon)
        self.assertEqual(len(daemon.jobs), 2)
        self.assertEqual(daemon.jobs[0]['model_id'], '1')
        self.assertEqual(daemon.jobs[0]['model_version_id'], '101')
        self.assertEqual(daemon.jobs[0]['base_model'], 'SD15')
        self.assertEqual(daemon.jobs[1]['filename'], 'f2')
        self.assertEqual(daemon.jobs[1]['model_type'], 'vae')
        self.assertEqual(daemon.jobs[1]['model_version_id'], '202')
        self.assertEqual(daemon.jobs[1]['base_model'], 'SDXL')

    def test_manifest_validation(self):
        # Fout pad: ontbrekende velden
        manifest = [{"modelId": "1", "modelVersionId": None, "model_type": "other", "baseModel": None}]
        with open('configs/test_manifest_invalid.json', 'w') as f:
            json.dump(manifest, f)
        daemon = DummyDaemon()
        process_manifest('configs/test_manifest_invalid.json', daemon)
        self.assertEqual(daemon.jobs[0]['url'], None)
        self.assertEqual(daemon.jobs[0]['model_type'], 'other')
        self.assertIsNone(daemon.jobs[0]['model_version_id'])
        self.assertIsNone(daemon.jobs[0]['base_model'])

if __name__ == '__main__':
    unittest.main()
