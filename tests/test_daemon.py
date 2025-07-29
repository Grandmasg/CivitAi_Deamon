import unittest
from loguru import logger
import os

from backend.daemon import make_queue_item, DownloadDaemon
import unittest.mock as mock

# Loguru test log setup
_test_log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(_test_log_dir, exist_ok=True)
logger.add(os.path.join(_test_log_dir, "test.log"), rotation="1 MB", retention=3, encoding="utf-8")

class TestDownloadDaemon(unittest.TestCase):
    def setUp(self):
        from backend.database import init_db
        init_db()
        self.daemon = DownloadDaemon(max_retries=1, download_dir='test_downloads', throttle=0)

    def test_make_queue_item(self):
        item = make_queue_item('id', 'url', 'file', 'sha', 1, 'checkpoint', model_version_id='ver999', base_model='SD15')
        self.assertEqual(item['model_id'], 'id')
        self.assertEqual(item['priority'], 1)
        self.assertEqual(item['retries'], 0)
        self.assertEqual(item['model_type'], 'checkpoint')
        self.assertEqual(item['model_version_id'], 'ver999')
        self.assertEqual(item['base_model'], 'SD15')

    def test_add_job(self):
        item = make_queue_item('id', 'url', 'file', model_type='vae', model_version_id='ver888', base_model='SDXL')
        self.daemon._download_file = lambda x: (True, 'dummy')
        self.daemon.add_job(item)
        self.assertFalse(self.daemon.queue.empty())
        self.assertEqual(item['model_type'], 'vae')
        self.assertEqual(item['model_version_id'], 'ver888')
        self.assertEqual(item['base_model'], 'SDXL')

    @mock.patch('backend.daemon.send_webhook', lambda *a, **kw: None)
    def test_process_item_success(self):
        # Simuleer een succesvolle download door _download_file te mocken als tuple
        item = make_queue_item('id', 'url', 'file', model_type='lora', model_version_id='ver777', base_model='SDXL')
        self.daemon._download_file = lambda x: (True, 'dummy')
        result = self.daemon.process_item(item)
        self.assertTrue(result)
        self.assertEqual(item['model_type'], 'lora')
        self.assertEqual(item['model_version_id'], 'ver777')
        self.assertEqual(item['base_model'], 'SDXL')

    @mock.patch('backend.daemon.send_webhook', lambda *a, **kw: None)
    def test_process_item_failure(self):
        # Simuleer een mislukte download door _download_file te mocken als tuple
        item = make_queue_item('id', 'url', 'file', model_type='vae', model_version_id='ver666', base_model='SDXL')
        self.daemon._download_file = lambda x: (False, 'dummy')
        result = self.daemon.process_item(item)
        self.assertFalse(result)
        self.assertEqual(item['model_type'], 'vae')
        self.assertEqual(item['model_version_id'], 'ver666')
        self.assertEqual(item['base_model'], 'SDXL')

    def test_pause_resume(self):
        self.daemon.pause()
        self.assertTrue(self.daemon.paused)
        self.daemon.resume()
        self.assertFalse(self.daemon.paused)

    def test_cancel(self):
        # Add a job and then cancel it
        item = make_queue_item('id', 'url', 'file', model_type='other')
        self.daemon.add_job(item)
        # Cancel does not require job_id, just cancels current
        self.daemon.cancel()
        # The queue should still have the job, but cancel_current is True
        self.assertTrue(self.daemon.cancel_current)
        self.assertEqual(item['model_type'], 'other')

if __name__ == '__main__':
    unittest.main()
