import unittest
import os
from database import log_download, log_error, downloads_per_day

class TestDatabaseLogging(unittest.TestCase):
    def test_base_model_metrics(self):
        from database import download_time_stats_per_base_model, file_size_stats_per_base_model, downloads_per_day_base_model_status
        # Insert multiple downloads with different base_models
        log_download('idA', 'verA', 'fileA', 'success', file_size=100, download_time=1.5, base_model='SDXL')
        log_download('idB', 'verB', 'fileB', 'success', file_size=200, download_time=2.5, base_model='SDXL')
        log_download('idC', 'verC', 'fileC', 'success', file_size=300, download_time=3.5, base_model='SD15')
        # download_time_stats_per_base_model
        stats = download_time_stats_per_base_model()
        base_models = {row[0]: row for row in stats}
        self.assertIn('SDXL', base_models)
        self.assertIn('SD15', base_models)
        # file_size_stats_per_base_model
        size_stats = file_size_stats_per_base_model()
        size_models = {row[0]: row for row in size_stats}
        self.assertIn('SDXL', size_models)
        self.assertIn('SD15', size_models)
        # downloads_per_day_base_model_status
        day_stats = downloads_per_day_base_model_status()
        found_sdxl = any(row[1] == 'SDXL' for row in day_stats)
        found_sd15 = any(row[1] == 'SD15' for row in day_stats)
        self.assertTrue(found_sdxl)
        self.assertTrue(found_sd15)
    def setUp(self):
        self.test_download_dir = os.path.join(os.path.dirname(__file__), '../test_download')
        os.makedirs(self.test_download_dir, exist_ok=True)
        self.db_path = os.path.join(self.test_download_dir, 'test_completed.db')
        os.environ['CIVITAI_DAEMON_DB_PATH'] = os.path.abspath(self.db_path)
        # Zorg dat database leeg is voor test
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        from database import init_db
        init_db()

    def test_log_download(self):
        # Test with base_model
        log_download('id1', 'ver1', 'file1', 'success', base_model='SDXL')
        from database import DB_PATH
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT base_model FROM downloads WHERE model_id=?', ('id1',))
        row = c.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 'SDXL')

    def test_log_error(self):
        log_error('id2', 'file2', 'fail')
        # Geen assert, maar check dat geen exception optreedt

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.test_download_dir):
            try:
                os.rmdir(self.test_download_dir)
            except OSError:
                pass
        # Unset na test
        if 'CIVITAI_DAEMON_DB_PATH' in os.environ:
            del os.environ['CIVITAI_DAEMON_DB_PATH']

if __name__ == '__main__':
    unittest.main()
