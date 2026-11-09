import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codepal import tools


class TestTools(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.path = lambda *a: os.path.join(self.ws, *a)

    def test_write_then_read(self):
        r = tools.write_file(self.ws, "a.txt", "hello\nworld")
        self.assertTrue(r["ok"])
        self.assertTrue(os.path.exists(self.path("a.txt")))
        r2 = tools.read_file(self.ws, "a.txt")
        self.assertTrue(r2["ok"])
        self.assertIn("hello", r2["content"])
        self.assertEqual(r2["lines"], 2)

    def test_edit_unique(self):
        tools.write_file(self.ws, "b.txt", "foo bar foo")
        r = tools.edit_file(self.ws, "b.txt", "bar", "BAZ")
        self.assertTrue(r["ok"])
        self.assertIn("foo BAZ foo", open(self.path("b.txt"), encoding="utf-8").read())

    def test_edit_ambiguous(self):
        tools.write_file(self.ws, "c.txt", "x x x")
        r = tools.edit_file(self.ws, "c.txt", "x", "y")
        self.assertFalse(r["ok"])
        self.assertIn("歧义", r["error"])

    def test_path_escape_blocked(self):
        r = tools.read_file(self.ws, "../../etc/passwd")
        self.assertFalse(r["ok"])
        self.assertIn("越界", r["error"])

    def test_bash(self):
        r = tools.run_bash(self.ws, "echo hello")
        self.assertTrue(r["ok"])
        self.assertIn("hello", r["output"])

    def test_dispatch(self):
        r = tools.dispatch("write_file", self.ws, {"path": "d.txt", "content": "z"})
        self.assertTrue(r["ok"])


if __name__ == "__main__":
    unittest.main()
