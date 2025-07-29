import unittest
import json
import os
from loguru import logger

# Loguru test log setup
_test_log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(_test_log_dir, exist_ok=True)
logger.add(os.path.join(_test_log_dir, "test.log"), rotation="1 MB", retention=3, encoding="utf-8")

class TestPortSelection(unittest.TestCase):
    def setUp(self):
        self.config_path = 'test_config.json'
        self.config = {
            "active_port": None
        }
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f)

    def test_port_update(self):
        # Simuleer poortkeuze en update
        port = 8101
        with open(self.config_path, 'r+') as f:
            config = json.load(f)
            config['active_port'] = port
            f.seek(0)
            json.dump(config, f)
            f.truncate()
        with open(self.config_path) as f:
            config = json.load(f)
        self.assertEqual(config['active_port'], 8101)

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

if __name__ == '__main__':
    unittest.main()
