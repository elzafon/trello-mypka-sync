import sys
import os
import unittest
from pathlib import PurePosixPath
from unittest.mock import MagicMock, patch

_mock_config = MagicMock()
_mock_config.PKA_REPO_PATH = "/fake/pka"
sys.modules["src.config"] = _mock_config

from src.parser import slugify, unique_path, parse_card  # noqa: E402

BASE_CARD = {
    "card_id": "abc123",
    "name": "My Test Card",
    "desc": "Some description",
    "url": "https://trello.com/c/abc123",
    "date_modified": "2026-06-27T12:00:00.000Z",
    "labels": [],
    "attachments": [],
}


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Oracle VM Setup"), "oracle-vm-setup")

    def test_special_chars_stripped(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")

    def test_multiple_spaces(self):
        self.assertEqual(slugify("a  b"), "a-b")

    def test_empty_returns_untitled(self):
        self.assertEqual(slugify("!!!"), "untitled")


class TestUniquePath(unittest.TestCase):
    def test_returns_path_when_no_conflict(self):
        path = unique_path("/some/folder", "my-file.md")
        self.assertTrue(path.endswith("my-file.md"))
        self.assertIn("some", path)
        self.assertIn("folder", path)

    def test_appends_counter_on_conflict(self):
        with patch("src.parser.os.path.exists") as mock_exists:
            mock_exists.side_effect = lambda p: p.replace("\\", "/").endswith("/folder/my-file.md")
            result = unique_path("/folder", "my-file.md")
            self.assertTrue(result.replace("\\", "/").endswith("/folder/my-file-2.md"))


class TestParseCard(unittest.TestCase):
    def _card(self, **kwargs):
        return {**BASE_CARD, **kwargs}

    def test_topic_path_and_frontmatter(self):
        card = self._card(list_name="topics")
        path, fm, _ = parse_card(card)
        self.assertIn("PKM/My Life/Topics", path)
        self.assertIn("my-test-card.md", path)
        self.assertIn("name: My Test Card", fm)
        self.assertNotIn("status:", fm)

    def test_project_has_status_active(self):
        card = self._card(list_name="projects")
        _, fm, _ = parse_card(card)
        self.assertIn("status: active", fm)

    def test_crm_uses_full_name_key(self):
        card = self._card(list_name="crm")
        _, fm, _ = parse_card(card)
        self.assertIn("full_name: My Test Card", fm)
        # ensure bare "name:" key is absent (full_name is the only name field)
        self.assertNotIn("\nname:", fm)

    def test_incoming_path_includes_year_month(self):
        card = self._card(list_name="incoming")
        path, fm, _ = parse_card(card)
        norm = path.replace("\\", "/")
        self.assertIn("PKM/Journal/2026/06", norm)
        self.assertIn("2026-06-27-my-test-card.md", norm)
        self.assertIn("source: trello", fm)
        self.assertIn("- inbox", fm)

    def test_body_with_desc_and_attachments(self):
        card = self._card(
            list_name="topics",
            desc="My desc",
            attachments=[{"name": "Link", "url": "https://example.com"}],
        )
        _, _, body = parse_card(card)
        self.assertIn("My desc", body)
        self.assertIn("## References", body)
        self.assertIn("[Link](https://example.com)", body)

    def test_body_empty_when_no_desc_no_attachments(self):
        card = self._card(list_name="topics", desc="", attachments=[])
        _, _, body = parse_card(card)
        self.assertEqual(body, "")

    def test_date_extracted_from_iso(self):
        card = self._card(list_name="goals", date_modified="2026-01-15T08:30:00.000Z")
        _, fm, _ = parse_card(card)
        self.assertIn("date: 2026-01-15", fm)


if __name__ == "__main__":
    unittest.main()
