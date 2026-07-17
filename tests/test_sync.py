import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

_mock_config = MagicMock()
_mock_config.PKA_REPO_PATH = "/fake/pka"
sys.modules["src.config"] = _mock_config

import sync  # noqa: E402
import src.guardrail as guardrail  # noqa: E402

CARD = {
    "card_id": "abc123",
    "name": "My Card",
    "desc": "desc",
    "list_name": "topics",
    "labels": [],
    "attachments": [],
    "url": "https://trello.com/c/abc123",
    "date_modified": "2026-06-27T12:00:00.000Z",
}
PATH = "/fake/pka/PKM/My Life/Topics/my-card.md"
FM = "---\nname: My Card\n---"
BODY = ""


def _pull_ok():
    return {"success": True, "message": "Already up to date."}


def _pull_fail():
    return {"success": False, "message": "git pull --rebase failed: conflict"}


def _push_ok():
    return {"success": True, "committed_files": [PATH], "message": "Sync from Trello: My Card"}


def _push_fail():
    return {"success": False, "committed_files": [], "message": "git push failed"}


def _archive_ok():
    return {"success": True, "card_id": "abc123", "message": "Archived: My Card"}


def _archive_fail():
    return {"success": False, "card_id": "abc123", "message": "Trello API error 429"}


def _mock_logger():
    return MagicMock()


class TestSyncRun(unittest.TestCase):
    """Every test here patches guardrail.STATE_PATH to a throwaway temp
    file. This is defense in depth: individual tests also mock
    sync.record_failure/record_success directly, but if a test ever
    forgets to, the real guardrail call must land on a scratch file, never
    on trello-mypka-sync's real state/failure_state.json."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._state_patch = patch.object(
            guardrail, "STATE_PATH",
            os.path.join(self._tmp.name, "failure_state.json"),
        )
        self._state_patch.start()
        self.addCleanup(self._state_patch.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_happy_path_full_pipeline(self):
        with patch("sync.pull_rebase", return_value=_pull_ok()), \
             patch("sync.fetch_cards", return_value=[CARD]), \
             patch("sync.parse_card", return_value=(PATH, FM, BODY)), \
             patch("sync.write_card", return_value=PATH), \
             patch("sync.push_cards", return_value=_push_ok()) as mock_push, \
             patch("sync.archive_card", return_value=_archive_ok()) as mock_archive, \
             patch("sync.record_success") as mock_record_success, \
             patch("sync.setup_logger", return_value=_mock_logger()), \
             patch("sync.log_event"):
            sync.run()
            mock_push.assert_called_once_with([PATH], ["My Card"])
            mock_archive.assert_called_once_with("abc123", "My Card")
            mock_record_success.assert_called_once_with("abc123")

    def test_no_cards_skips_push_and_archive(self):
        with patch("sync.pull_rebase", return_value=_pull_ok()), \
             patch("sync.fetch_cards", return_value=[]), \
             patch("sync.push_cards") as mock_push, \
             patch("sync.archive_card") as mock_archive, \
             patch("sync.setup_logger", return_value=_mock_logger()), \
             patch("sync.log_event"):
            sync.run()
            mock_push.assert_not_called()
            mock_archive.assert_not_called()

    def test_fetch_failure_exits_with_1(self):
        with patch("sync.pull_rebase", return_value=_pull_ok()), \
             patch("sync.fetch_cards", side_effect=Exception("connection refused")), \
             patch("sync.setup_logger", return_value=_mock_logger()), \
             patch("sync.log_event"):
            with self.assertRaises(SystemExit) as ctx:
                sync.run()
            self.assertEqual(ctx.exception.code, 1)

    def test_pull_rebase_failure_is_non_fatal(self):
        """A failed pre-sync pull/rebase logs a warning but the run still
        proceeds to fetch/write/push — matches pax-vm's non-blocking
        pull-failure convention."""
        with patch("sync.pull_rebase", return_value=_pull_fail()), \
             patch("sync.fetch_cards", return_value=[]) as mock_fetch, \
             patch("sync.setup_logger", return_value=_mock_logger()) as mock_setup, \
             patch("sync.log_event"):
            sync.run()
            mock_fetch.assert_called_once()
            mock_setup.return_value.warning.assert_called_once()

    def test_push_failure_does_not_archive_and_exits_with_1(self):
        with patch("sync.pull_rebase", return_value=_pull_ok()), \
             patch("sync.fetch_cards", return_value=[CARD]), \
             patch("sync.parse_card", return_value=(PATH, FM, BODY)), \
             patch("sync.write_card", return_value=PATH), \
             patch("sync.push_cards", return_value=_push_fail()), \
             patch("sync.archive_card") as mock_archive, \
             patch("sync.setup_logger", return_value=_mock_logger()), \
             patch("sync.log_event"):
            with self.assertRaises(SystemExit) as ctx:
                sync.run()
            self.assertEqual(ctx.exception.code, 1)
            mock_archive.assert_not_called()

    def test_push_failure_records_guardrail_failure_per_card(self):
        with patch("sync.pull_rebase", return_value=_pull_ok()), \
             patch("sync.fetch_cards", return_value=[CARD]), \
             patch("sync.parse_card", return_value=(PATH, FM, BODY)), \
             patch("sync.write_card", return_value=PATH), \
             patch("sync.push_cards", return_value=_push_fail()), \
             patch("sync.archive_card"), \
             patch("sync.record_failure", return_value=(1, False)) as mock_record_failure, \
             patch("sync.alert") as mock_alert, \
             patch("sync.setup_logger", return_value=_mock_logger()), \
             patch("sync.log_event"):
            with self.assertRaises(SystemExit):
                sync.run()
            mock_record_failure.assert_called_once_with("abc123", "My Card", "push")
            mock_alert.assert_not_called()

    def test_archive_failure_alerts_once_threshold_is_crossed(self):
        with patch("sync.pull_rebase", return_value=_pull_ok()), \
             patch("sync.fetch_cards", return_value=[CARD]), \
             patch("sync.parse_card", return_value=(PATH, FM, BODY)), \
             patch("sync.write_card", return_value=PATH), \
             patch("sync.push_cards", return_value=_push_ok()), \
             patch("sync.archive_card", return_value=_archive_fail()), \
             patch("sync.record_failure", return_value=(4, True)) as mock_record_failure, \
             patch("sync.alert") as mock_alert, \
             patch("sync.setup_logger", return_value=_mock_logger()), \
             patch("sync.log_event"):
            sync.run()
            mock_record_failure.assert_called_once_with("abc123", "My Card", "archive")
            mock_alert.assert_called_once()
            self.assertIn("abc123", mock_alert.call_args[0][0])

    def test_per_card_write_error_continues_with_others(self):
        card2 = {**CARD, "card_id": "def456", "name": "Card 2"}
        path2 = "/fake/pka/PKM/My Life/Topics/card-2.md"

        def parse_side(card):
            if card["card_id"] == "abc123":
                raise ValueError("parse failed")
            return (path2, FM, BODY)

        with patch("sync.pull_rebase", return_value=_pull_ok()), \
             patch("sync.fetch_cards", return_value=[CARD, card2]), \
             patch("sync.parse_card", side_effect=parse_side), \
             patch("sync.write_card", return_value=path2), \
             patch("sync.push_cards", return_value={"success": True, "committed_files": [path2], "message": "ok"}) as mock_push, \
             patch("sync.archive_card", return_value={"success": True, "card_id": "def456", "message": "Archived: Card 2"}) as mock_archive, \
             patch("sync.record_success"), \
             patch("sync.setup_logger", return_value=_mock_logger()), \
             patch("sync.log_event"):
            sync.run()
            mock_push.assert_called_once_with([path2], ["Card 2"])
            mock_archive.assert_called_once_with("def456", "Card 2")

    def test_all_cards_fail_to_write_skips_push(self):
        with patch("sync.pull_rebase", return_value=_pull_ok()), \
             patch("sync.fetch_cards", return_value=[CARD]), \
             patch("sync.parse_card", side_effect=ValueError("bad card")), \
             patch("sync.push_cards") as mock_push, \
             patch("sync.archive_card") as mock_archive, \
             patch("sync.setup_logger", return_value=_mock_logger()), \
             patch("sync.log_event"):
            sync.run()
            mock_push.assert_not_called()
            mock_archive.assert_not_called()


if __name__ == "__main__":
    unittest.main()
