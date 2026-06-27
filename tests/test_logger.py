import os
import tempfile
import unittest

from src.logger import setup_logger, log_event


class TestLogger(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "sync.log")
        # unique logger name per test instance to avoid handler accumulation
        self._name = f"sync_test_{id(self)}"

    def _logger(self):
        return setup_logger(self.log_path, name=self._name)

    def test_creates_log_file_on_first_write(self):
        logger = self._logger()
        logger.info("hello")
        self.assertTrue(os.path.exists(self.log_path))

    def test_log_event_success_writes_info(self):
        logger = self._logger()
        log_event(logger, "abc123", "My Card", "archive", "Archived: My Card", success=True)
        with open(self.log_path) as f:
            content = f.read()
        self.assertIn("INFO", content)
        self.assertIn("card_id=abc123", content)
        self.assertIn('name="My Card"', content)
        self.assertIn("action=archive", content)
        self.assertIn("Archived: My Card", content)

    def test_log_event_failure_writes_error(self):
        logger = self._logger()
        log_event(logger, "def456", "Other Card", "git_push", "git push failed", success=False)
        with open(self.log_path) as f:
            content = f.read()
        self.assertIn("ERROR", content)
        self.assertIn("card_id=def456", content)
        self.assertIn("git push failed", content)

    def test_setup_logger_idempotent_single_handler(self):
        logger1 = setup_logger(self.log_path, name=self._name)
        logger2 = setup_logger(self.log_path, name=self._name)
        self.assertIs(logger1, logger2)
        self.assertEqual(len(logger1.handlers), 1)

    def test_creates_parent_directory_if_missing(self):
        nested_path = os.path.join(self.tmpdir, "logs", "nested", "sync.log")
        logger = setup_logger(nested_path, name=f"{self._name}_nested")
        logger.info("test")
        self.assertTrue(os.path.exists(nested_path))


if __name__ == "__main__":
    unittest.main()
