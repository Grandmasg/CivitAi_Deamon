import unittest
import os
from database import log_download, log_error, downloads_per_day

class TestDatabaseLogging(unittest.TestCase):
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
        log_download('id1', 'ver1', 'file1', 'success')
        result = downloads_per_day()
        self.assertTrue(len(result) >= 1)

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
