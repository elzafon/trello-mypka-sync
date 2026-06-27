import sys
import unittest
from unittest.mock import patch, MagicMock

# Inject a fake config before src.fetcher is imported so no .env is needed
_mock_config = MagicMock()
_mock_config.TRELLO_AUTH = {"key": "fake_key", "token": "fake_token"}
_mock_config.TRELLO_LISTS = {
    "topics":   "list_topics",
    "projects": "list_projects",
    "goals":    "list_goals",
    "crm":      "list_crm",
    "incoming": "list_incoming",
}
sys.modules["src.config"] = _mock_config

from src.fetcher import fetch_cards  # noqa: E402 — must come after mock

SAMPLE_CARD = {
    "id": "abc123",
    "name": "Test Card",
    "desc": "A description",
    "url": "https://trello.com/c/abc123",
    "dateLastActivity": "2026-06-27T12:00:00.000Z",
    "labels": [{"name": "important", "color": "red"}],
    "attachments": [{"name": "Link", "url": "https://example.com"}],
}


class TestFetchCards(unittest.TestCase):
    @patch("src.fetcher.requests.get")
    def test_returns_structured_cards(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [SAMPLE_CARD]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        cards = fetch_cards()

        # One card returned per list (5 lists)
        self.assertEqual(len(cards), 5)

        first = cards[0]
        self.assertEqual(first["card_id"], "abc123")
        self.assertEqual(first["name"], "Test Card")
        self.assertEqual(first["desc"], "A description")
        self.assertEqual(first["url"], "https://trello.com/c/abc123")
        self.assertEqual(first["date_modified"], "2026-06-27T12:00:00.000Z")
        self.assertEqual(first["labels"], ["important"])
        self.assertEqual(first["attachments"], [{"name": "Link", "url": "https://example.com"}])

    @patch("src.fetcher.requests.get")
    def test_skips_attachments_without_url(self, mock_get):
        card = {**SAMPLE_CARD, "attachments": [{"name": "No URL"}]}
        mock_resp = MagicMock()
        mock_resp.json.return_value = [card]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        cards = fetch_cards()
        self.assertEqual(cards[0]["attachments"], [])

    @patch("src.fetcher.requests.get")
    def test_empty_list_returns_no_cards(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        cards = fetch_cards()
        self.assertEqual(cards, [])


if __name__ == "__main__":
    unittest.main()
