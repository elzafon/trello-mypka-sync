import sys
import os
import unittest
import yaml
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

    def test_incoming_stages_flat_in_team_inbox(self):
        # incoming is a STAGING area (WS-005 Stream B), not the knowledge base.
        # Flat on purpose: no YYYY/MM, so "is the inbox empty?" stays
        # answerable at a glance.
        card = self._card(list_name="incoming")
        path, fm, _ = parse_card(card)
        norm = path.replace("\\", "/")
        self.assertIn("Team Inbox/2026-06-27-my-test-card.md", norm)
        self.assertNotIn("PKM/Journal", norm)
        self.assertNotIn("2026/06", norm)
        self.assertIn("source: trello", fm)
        self.assertIn("- inbox", fm)

    def test_journal_path_includes_year_month(self):
        card = self._card(list_name="journal")
        path, fm, _ = parse_card(card)
        norm = path.replace("\\", "/")
        self.assertIn("PKM/Journal/2026/06", norm)
        self.assertIn("2026-06-27-my-test-card.md", norm)
        self.assertIn("source: trello", fm)
        self.assertIn("- journal", fm)

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

    # Rerouted 2026-07-23: research stages in Team Inbox/ instead of writing
    # into PKM/My Life/Topics, because the pax-vm job that was meant to complete
    # those notes is frozen. See parser.LIST_FOLDER_MAP.
    def test_research_path_in_team_inbox_flat(self):
        card = self._card(list_name="research")
        path, _, _ = parse_card(card)
        norm = path.replace("\\", "/")
        self.assertIn("Team Inbox", norm)
        self.assertNotIn("PKM/My Life/Topics", norm)
        # Flat — no YYYY/MM nesting — and date-prefixed like `incoming`.
        # BASE_CARD.date_modified is 2026-06-27.
        self.assertIn("2026-06-27-my-test-card.md", norm)
        self.assertNotIn("Team Inbox/2026/", norm)

    def test_research_frontmatter_has_tag_and_no_status(self):
        card = self._card(list_name="research")
        _, fm, _ = parse_card(card)
        # research_status had exactly one consumer (pax-vm) and it is disabled.
        self.assertNotIn("research_status", fm)
        self.assertIn("tags:", fm)
        self.assertIn("  - research", fm)
        self.assertIn("name: My Test Card", fm)

    def test_research_body_has_no_pax_section(self):
        card = self._card(list_name="research", desc="Some context")
        _, _, body = parse_card(card)
        self.assertIn("Some context", body)
        self.assertNotIn("## Pax Research", body)
        self.assertNotIn("_Pending..._", body)

    def test_research_body_empty_when_no_desc_no_attachments(self):
        card = self._card(list_name="research", desc="", attachments=[])
        _, _, body = parse_card(card)
        self.assertEqual(body, "")

    def test_research_body_with_attachments_ends_at_references(self):
        card = self._card(
            list_name="research",
            desc="",
            attachments=[{"name": "Ref", "url": "https://example.com"}],
        )
        _, _, body = parse_card(card)
        self.assertIn("## References", body)
        self.assertNotIn("## Pax Research", body)


class TestResearchModeAndUrl(unittest.TestCase):
    """Regression tests for the source_url/research_url mismatch bug (2026-07-02):
    source_url must always stay the Trello permalink (origin tracking); a real
    fetch target only ever lands in research_url, and only when the card is
    confidently "just a link", never when a URL is merely mentioned in passing
    inside a longer pasted body."""

    def _card(self, **kwargs):
        return {**BASE_CARD, **kwargs}

    def test_source_url_is_always_trello_permalink(self):
        card = self._card(
            list_name="research",
            name="https://github.com/org/repo",
            desc="",
        )
        _, fm, _ = parse_card(card)
        self.assertIn(f"source_url: {BASE_CARD['url']}", fm)

    def test_sole_short_link_sets_fetch_mode_and_research_url(self):
        card = self._card(
            list_name="research",
            name="https://github.com/org/repo check this out",
            desc="[https://github.com/org/repo](https://github.com/org/repo)\n\nworth implementing?",
        )
        _, fm, _ = parse_card(card)
        self.assertIn("research_mode: fetch", fm)
        self.assertIn("research_url: https://github.com/org/repo", fm)

    def test_url_mentioned_in_passing_sets_body_mode_no_research_url(self):
        long_text = " ".join(["filler word"] * 100)
        card = self._card(
            list_name="research",
            name="check these prompts and comment",
            desc=f"{long_text} I feed the outputs into Ranked AI. http://www.Ranked.ai does the rest. {long_text}",
        )
        _, fm, _ = parse_card(card)
        self.assertIn("research_mode: body", fm)
        self.assertNotIn("research_url:", fm)

    def test_url_in_bare_name_no_desc_sets_fetch_mode(self):
        card = self._card(
            list_name="research",
            name="https://github.com/msitarzewski/agency-agents",
            desc="",
            attachments=[],
        )
        _, fm, _ = parse_card(card)
        self.assertIn("research_mode: fetch", fm)
        self.assertIn("research_url: https://github.com/msitarzewski/agency-agents", fm)

    def test_no_url_anywhere_sets_body_mode(self):
        card = self._card(list_name="research", name="think about this", desc="no links here")
        _, fm, _ = parse_card(card)
        self.assertIn("research_mode: body", fm)
        self.assertNotIn("research_url:", fm)

    def test_multiple_urls_sets_body_mode(self):
        card = self._card(
            list_name="research",
            desc="compare https://a.example.com and https://b.example.com",
        )
        _, fm, _ = parse_card(card)
        self.assertIn("research_mode: body", fm)
        self.assertNotIn("research_url:", fm)

    def test_explicit_fetch_label_overrides_heuristic(self):
        long_text = " ".join(["filler"] * 100)
        card = self._card(
            list_name="research",
            labels=["research-fetch"],
            desc=f"{long_text} https://example.com/article {long_text}",
        )
        _, fm, _ = parse_card(card)
        self.assertIn("research_mode: fetch", fm)
        self.assertIn("research_url: https://example.com/article", fm)

    def test_explicit_body_label_overrides_heuristic(self):
        card = self._card(
            list_name="research",
            labels=["research-body"],
            desc="https://example.com/short",
        )
        _, fm, _ = parse_card(card)
        self.assertIn("research_mode: body", fm)
        self.assertNotIn("research_url:", fm)


class TestFrontmatterYamlSafety(unittest.TestCase):
    """Regression tests for a second bug found while fixing the first:
    a card name ending in a colon (e.g. Trello title "...and comment:")
    produced invalid YAML via naive f-string interpolation, silently
    excluding that file from every future frontmatter.load() scan (pax-vm's
    pending-file scanner logs a warning and skips unparsable files)."""

    def _card(self, **kwargs):
        return {**BASE_CARD, **kwargs}

    def _parsed_frontmatter(self, card):
        _, fm, _ = parse_card(card)
        yaml_body = fm.strip().strip("-").strip()
        return yaml.safe_load(yaml_body)

    def test_name_with_trailing_colon_round_trips(self):
        card = self._card(list_name="topics", name="check these prompts list and comment:")
        data = self._parsed_frontmatter(card)
        self.assertEqual(data["name"], "check these prompts list and comment:")

    def test_name_with_quotes_round_trips(self):
        card = self._card(list_name="topics", name='A card called "quoted" title')
        data = self._parsed_frontmatter(card)
        self.assertEqual(data["name"], 'A card called "quoted" title')

    def test_unicode_name_round_trips(self):
        card = self._card(list_name="topics", name="מנקה חלון רובוטי")
        data = self._parsed_frontmatter(card)
        self.assertEqual(data["name"], "מנקה חלון רובוטי")

    def test_research_card_with_colon_name_is_valid_yaml(self):
        card = self._card(
            list_name="research",
            name="check these prompts list and comment:",
            desc="1. Prompt one\n2. Prompt two",
        )
        data = self._parsed_frontmatter(card)
        self.assertEqual(data["name"], "check these prompts list and comment:")
        # research_status dropped 2026-07-23 — its only consumer (pax-vm) is off.
        # The YAML-safety regression this test guards is the colon in the name.
        self.assertNotIn("research_status", data)
        self.assertEqual(data["research_mode"], "body")


class TestChecklists(unittest.TestCase):
    """Trello card Checklists render as markdown task-list checkboxes in the
    note body (decided 2026-07-19, project trello-mypka-sync): `- [ ] item`
    for an incomplete item, `- [x] item` for a complete one, preserving the
    subtask structure written on the card."""

    def _card(self, **kwargs):
        return {**BASE_CARD, **kwargs}

    def test_incomplete_items_render_as_empty_checkboxes(self):
        card = self._card(
            list_name="topics",
            desc="",
            checklists=[{"name": "Steps", "items": [
                {"name": "First step", "checked": False},
                {"name": "Second step", "checked": False},
            ]}],
        )
        _, _, body = parse_card(card)
        self.assertIn("- [ ] First step", body)
        self.assertIn("- [ ] Second step", body)

    def test_mixed_complete_and_incomplete_items(self):
        card = self._card(
            list_name="topics",
            desc="",
            checklists=[{"name": "Steps", "items": [
                {"name": "Done thing", "checked": True},
                {"name": "Todo thing", "checked": False},
            ]}],
        )
        _, _, body = parse_card(card)
        self.assertIn("- [x] Done thing", body)
        self.assertIn("- [ ] Todo thing", body)

    def test_checklist_name_becomes_heading(self):
        card = self._card(
            list_name="topics",
            desc="",
            checklists=[{"name": "My Checklist", "items": [
                {"name": "a", "checked": False},
            ]}],
        )
        _, _, body = parse_card(card)
        self.assertIn("## My Checklist", body)

    def test_unnamed_checklist_falls_back_to_generic_heading(self):
        card = self._card(
            list_name="topics",
            desc="",
            checklists=[{"name": "", "items": [{"name": "a", "checked": False}]}],
        )
        _, _, body = parse_card(card)
        self.assertIn("## Checklist", body)

    def test_no_checklist_key_produces_no_checkboxes(self):
        card = self._card(list_name="topics", desc="Just text")
        _, _, body = parse_card(card)
        self.assertNotIn("- [ ]", body)
        self.assertNotIn("- [x]", body)
        self.assertEqual(body, "Just text")

    def test_empty_checklist_is_skipped(self):
        card = self._card(
            list_name="topics",
            desc="Body text",
            checklists=[{"name": "Empty", "items": []}],
        )
        _, _, body = parse_card(card)
        self.assertNotIn("## Empty", body)
        self.assertEqual(body, "Body text")

    def test_checklist_sits_after_desc_before_references(self):
        card = self._card(
            list_name="topics",
            desc="Description here",
            checklists=[{"name": "Steps", "items": [
                {"name": "step one", "checked": False},
            ]}],
            attachments=[{"name": "Ref", "url": "https://example.com"}],
        )
        _, _, body = parse_card(card)
        self.assertLess(body.index("Description here"), body.index("- [ ] step one"))
        self.assertLess(body.index("- [ ] step one"), body.index("## References"))

    def test_multiple_checklists_all_rendered(self):
        card = self._card(
            list_name="topics",
            desc="",
            checklists=[
                {"name": "List A", "items": [{"name": "a1", "checked": True}]},
                {"name": "List B", "items": [{"name": "b1", "checked": False}]},
            ],
        )
        _, _, body = parse_card(card)
        self.assertIn("## List A", body)
        self.assertIn("- [x] a1", body)
        self.assertIn("## List B", body)
        self.assertIn("- [ ] b1", body)

    def test_checklist_on_research_card_renders_without_pax_section(self):
        # The Pax Research placeholder was removed 2026-07-23 along with
        # research_status; checklists must still render on a research card.
        card = self._card(
            list_name="research",
            desc="",
            checklists=[{"name": "Steps", "items": [
                {"name": "do x", "checked": False},
            ]}],
        )
        _, _, body = parse_card(card)
        self.assertIn("## Steps", body)
        self.assertIn("- [ ] do x", body)
        self.assertNotIn("## Pax Research", body)


if __name__ == "__main__":
    unittest.main()
