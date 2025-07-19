import unittest

from daemon import make_queue_item, DownloadDaemon
import unittest.mock as mock

class TestDownloadDaemon(unittest.TestCase):
    def setUp(self):
        self.daemon = DownloadDaemon(max_retries=1, download_dir='test_downloads', throttle=0)

    def test_make_queue_item(self):
        item = make_queue_item('id', 'url', 'file', 'sha', 1)
        self.assertEqual(item['model_id'], 'id')
        self.assertEqual(item['priority'], 1)
        self.assertEqual(item['retries'], 0)

    def test_add_job(self):
        item = make_queue_item('id', 'url', 'file')
        self.daemon.add_job(item)
        self.assertFalse(self.daemon.queue.empty())

    @mock.patch('daemon.send_webhook', lambda *a, **kw: None)
    def test_process_item_success(self):
        # Simulate a successful download by mocking _download_file
        item = make_queue_item('id', 'url', 'file')
        self.daemon._download_file = lambda x: True
        result = self.daemon.process_item(item)
        self.assertTrue(result)

    @mock.patch('daemon.send_webhook', lambda *a, **kw: None)
    def test_process_item_failure(self):
        # Simulate a failed download by mocking _download_file
        item = make_queue_item('id', 'url', 'file')
        self.daemon._download_file = lambda x: False
        result = self.daemon.process_item(item)
        self.assertFalse(result)

    def test_pause_resume(self):
        self.daemon.pause()
        self.assertTrue(self.daemon.paused)
        self.daemon.resume()
        self.assertFalse(self.daemon.paused)

    def test_cancel(self):
        # Add a job and then cancel it
        item = make_queue_item('id', 'url', 'file')
        self.daemon.add_job(item)
        # Cancel does not require job_id, just cancels current
        self.daemon.cancel()
        # The queue should still have the job, but cancel_current is True
        self.assertTrue(self.daemon.cancel_current)

if __name__ == '__main__':
    unittest.main()
