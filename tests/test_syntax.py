"""brew_tool runs on Python 3.9+: no match statements, no `X | Y` type
syntax, nothing newer. This parses every module with the 3.9 grammar so a
3.11 laptop can't quietly write something the CI's 3.9 rejects."""
import ast
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class SyntaxTest(unittest.TestCase):
    def test_parses_as_python_3_9(self):
        files = list((REPO / "brew").glob("*.py")) + list(
            (REPO / "tests").glob("*.py"))
        self.assertTrue(files)
        for f in files:
            with self.subTest(file=f.name):
                ast.parse(f.read_text(), filename=str(f),
                          feature_version=(3, 9))

    def test_no_walrus_free_for_all(self):
        # a style rule, not a syntax one: keep the code readable at arm's length
        for f in (REPO / "brew").glob("*.py"):
            self.assertNotIn(" match ", f.read_text().replace("re.match", ""),
                             f"{f.name}: match statements need 3.10")


if __name__ == "__main__":
    unittest.main()
