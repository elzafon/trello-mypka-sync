import os
import sys
import tempfile
import unittest

# writer.py has no config import — no mock needed
from src.writer import write_card


class TestWriteCard(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_writes_file_with_frontmatter_and_body(self):
        path = os.path.join(self.tmpdir, "test.md")
        fm = "---\nname: Test\n---"
        body = "Some content."
        write_card(path, fm, body)

        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("---\nname: Test\n---", content)
        self.assertIn("Some content.", content)

    def test_creates_parent_directories(self):
        path = os.path.join(self.tmpdir, "deep", "nested", "file.md")
        write_card(path, "---\nname: X\n---", "")
        self.assertTrue(os.path.exists(path))

    def test_no_body_writes_frontmatter_only(self):
        path = os.path.join(self.tmpdir, "no-body.md")
        write_card(path, "---\nname: X\n---", "")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("\n\n", content)

    def test_returns_target_path(self):
        path = os.path.join(self.tmpdir, "ret.md")
        result = write_card(path, "---\nname: X\n---", "body")
        self.assertEqual(result, path)

    def test_file_is_utf8(self):
        path = os.path.join(self.tmpdir, "utf8.md")
        write_card(path, "---\nname: שלום\n---", "")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("שלום", content)


if __name__ == "__main__":
    unittest.main()
