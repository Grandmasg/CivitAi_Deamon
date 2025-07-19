import unittest
import os
from database import log_download, log_error, downloads_per_day

class TestDatabaseLogging(unittest.TestCase):
    def setUp(self):
        self.db_path = os.path.join(os.path.dirname(__file__), '../data/completed.db')
        # Zorg dat database leeg is voor test
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        from database import init_db
        init_db()

    def test_log_download(self):
        log_download('id1', 'file1', 'success')
        result = downloads_per_day()
        self.assertTrue(len(result) >= 1)

    def test_log_error(self):
        log_error('id2', 'file2', 'fail')
        # Geen assert, maar check dat geen exception optreedt

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

if __name__ == '__main__':
    unittest.main()
