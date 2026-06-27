import sys
import subprocess
import unittest
from unittest.mock import MagicMock, patch, call

_mock_config = MagicMock()
_mock_config.PKA_REPO_PATH = "/fake/pka"
sys.modules["src.config"] = _mock_config

from src.git_push import push_cards  # noqa: E402

REPO = "/fake/pka"
FILES = ["/fake/pka/PKM/My Life/Topics/foo.md"]
NAMES = ["Foo Topic"]


def _ok(stdout="", stderr=""):
    r = MagicMock()
    r.returncode = 0
    r.stdout = stdout
    r.stderr = stderr
    return r


def _fail(stdout="", stderr="error msg"):
    r = MagicMock()
    r.returncode = 1
    r.stdout = stdout
    r.stderr = stderr
    return r


class TestPushCards(unittest.TestCase):

    def test_empty_files_returns_nothing_to_commit(self):
        result = push_cards([], [])
        self.assertTrue(result["success"])
        self.assertEqual(result["committed_files"], [])
        self.assertEqual(result["message"], "Nothing to commit")

    @patch("src.git_push.subprocess.run")
    def test_happy_path_all_three_commands_succeed(self, mock_run):
        mock_run.side_effect = [_ok(), _ok(), _ok()]
        result = push_cards(FILES, NAMES)

        self.assertTrue(result["success"])
        self.assertEqual(result["committed_files"], FILES)
        self.assertIn("Sync from Trello:", result["message"])
        self.assertIn("Foo Topic", result["message"])

        calls = mock_run.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertIn("add", calls[0][0][0])
        self.assertIn("commit", calls[1][0][0])
        self.assertIn("push", calls[2][0][0])

    @patch("src.git_push.subprocess.run")
    def test_git_add_failure_returns_error(self, mock_run):
        mock_run.side_effect = [_fail(stderr="permission denied")]
        result = push_cards(FILES, NAMES)

        self.assertFalse(result["success"])
        self.assertIn("git add failed", result["message"])
        self.assertEqual(mock_run.call_count, 1)

    @patch("src.git_push.subprocess.run")
    def test_nothing_to_commit_is_not_an_error(self, mock_run):
        mock_run.side_effect = [
            _ok(),
            _fail(stdout="nothing to commit, working tree clean"),
        ]
        result = push_cards(FILES, NAMES)

        self.assertTrue(result["success"])
        self.assertEqual(result["committed_files"], [])
        self.assertEqual(result["message"], "Nothing to commit")
        self.assertEqual(mock_run.call_count, 2)

    @patch("src.git_push.subprocess.run")
    def test_git_push_failure_after_commit(self, mock_run):
        mock_run.side_effect = [_ok(), _ok(), _fail(stderr="remote: permission denied")]
        result = push_cards(FILES, NAMES)

        self.assertFalse(result["success"])
        self.assertIn("git push failed", result["message"])
        self.assertEqual(result["committed_files"], FILES)

    @patch("src.git_push.subprocess.run")
    def test_commit_message_truncates_long_card_list(self, mock_run):
        mock_run.side_effect = [_ok(), _ok(), _ok()]
        many_names = [f"Card {i}" for i in range(8)]
        result = push_cards(["/fake/pka/file.md"] * 8, many_names)

        self.assertIn("(+3 more)", result["message"])

    @patch("src.git_push.subprocess.run")
    def test_git_called_with_correct_repo_path(self, mock_run):
        mock_run.side_effect = [_ok(), _ok(), _ok()]
        push_cards(FILES, NAMES)

        for c in mock_run.call_args_list:
            cmd = c[0][0]
            self.assertEqual(cmd[1], "-C")
            self.assertEqual(cmd[2], REPO)


if __name__ == "__main__":
    unittest.main()
