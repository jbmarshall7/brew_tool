"""brew_tool runs on Python 3.9+. This parses every module with the 3.9
grammar so a match statement cannot slip in from a 3.11 laptop; runtime-only
3.10+ features (X | Y annotations, zip(strict=...)) are what the 3.9 job in
the CI matrix is for."""
import ast
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


if __name__ == "__main__":
    unittest.main()
