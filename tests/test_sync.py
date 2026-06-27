import sys
import unittest
from unittest.mock import MagicMock, patch

_mock_config = MagicMock()
_mock_config.PKA_REPO_PATH = "/fake/pka"
sys.modules["src.config"] = _mock_config

import sync  # noqa: E402

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


def _push_ok():
    return {"success": True, "committed_files": [PATH], "message": "Sync from Trello: My Card"}


def _push_fail():
    return {"success": False, "committed_files": [], "message": "git push failed"}


def _archive_ok():
    return {"success": True, "card_id": "abc123", "message": "Archived: My Card"}


def _mock_logger():
    return MagicMock()


class TestSyncRun(unittest.TestCase):

    def test_happy_path_full_pipeline(self):
        with patch("sync.fetch_cards", return_value=[CARD]), \
             patch("sync.parse_card", return_value=(PATH, FM, BODY)), \
             patch("sync.write_card", return_value=PATH), \
             patch("sync.push_cards", return_value=_push_ok()) as mock_push, \
             patch("sync.archive_card", return_value=_archive_ok()) as mock_archive, \
             patch("sync.setup_logger", return_value=_mock_logger()), \
             patch("sync.log_event"):
            sync.run()
            mock_push.assert_called_once_with([PATH], ["My Card"])
            mock_archive.assert_called_once_with("abc123", "My Card")

    def test_no_cards_skips_push_and_archive(self):
        with patch("sync.fetch_cards", return_value=[]), \
             patch("sync.push_cards") as mock_push, \
             patch("sync.archive_card") as mock_archive, \
             patch("sync.setup_logger", return_value=_mock_logger()), \
             patch("sync.log_event"):
            sync.run()
            mock_push.assert_not_called()
            mock_archive.assert_not_called()

    def test_fetch_failure_exits_with_1(self):
        with patch("sync.fetch_cards", side_effect=Exception("connection refused")), \
             patch("sync.setup_logger", return_value=_mock_logger()), \
             patch("sync.log_event"):
            with self.assertRaises(SystemExit) as ctx:
                sync.run()
            self.assertEqual(ctx.exception.code, 1)

    def test_push_failure_does_not_archive_and_exits_with_1(self):
        with patch("sync.fetch_cards", return_value=[CARD]), \
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

    def test_per_card_write_error_continues_with_others(self):
        card2 = {**CARD, "card_id": "def456", "name": "Card 2"}
        path2 = "/fake/pka/PKM/My Life/Topics/card-2.md"

        def parse_side(card):
            if card["card_id"] == "abc123":
                raise ValueError("parse failed")
            return (path2, FM, BODY)

        with patch("sync.fetch_cards", return_value=[CARD, card2]), \
             patch("sync.parse_card", side_effect=parse_side), \
             patch("sync.write_card", return_value=path2), \
             patch("sync.push_cards", return_value={"success": True, "committed_files": [path2], "message": "ok"}) as mock_push, \
             patch("sync.archive_card", return_value=_archive_ok()) as mock_archive, \
             patch("sync.setup_logger", return_value=_mock_logger()), \
             patch("sync.log_event"):
            sync.run()
            mock_push.assert_called_once_with([path2], ["Card 2"])
            mock_archive.assert_called_once_with("def456", "Card 2")

    def test_all_cards_fail_to_write_skips_push(self):
        with patch("sync.fetch_cards", return_value=[CARD]), \
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
