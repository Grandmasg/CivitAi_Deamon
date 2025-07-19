import unittest
from daemon import make_queue_item, DownloadDaemon

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

    def test_process_item_success(self):
        # Simulate a successful download by mocking _download_file
        item = make_queue_item('id', 'url', 'file')
        self.daemon._download_file = lambda x: True
        result = self.daemon.process_item(item)
        self.assertTrue(result)

    def test_process_item_failure(self):
        # Simulate a failed download by mocking _download_file
        item = make_queue_item('id', 'url', 'file')
        self.daemon._download_file = lambda x: False
        result = self.daemon.process_item(item)
        self.assertFalse(result)

    def test_pause_resume(self):
        self.daemon.pause()
        self.assertTrue(self.daemon._paused)
        self.daemon.resume()
        self.assertFalse(self.daemon._paused)

    def test_cancel(self):
        # Add a job and then cancel it
        item = make_queue_item('id', 'url', 'file')
        self.daemon.add_job(item)
        self.daemon.cancel(item['job_id'])
        # The queue should be empty after cancel
        self.assertTrue(self.daemon.queue.empty())

if __name__ == '__main__':
    unittest.main()
