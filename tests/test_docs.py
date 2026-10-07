"""The reference pages cover what the code offers. Fails when a command, an option or a
Project method is added without a line in docs/reference/."""
import unittest
from pathlib import Path

from file2records import Project, cli

DOCS = Path(__file__).resolve().parents[1] / "docs" / "reference"


@unittest.skipUnless(DOCS.is_dir(), "docs/ is not shipped in the sdist's tests")
class ReferenceTests(unittest.TestCase):
    def test_every_command_and_option_is_documented(self):
        page = (DOCS / "cli.md").read_text(encoding="utf-8")
        sub = next(a for a in cli.build_parser()._actions if a.dest == "command")
        for name, parser in sub.choices.items():
            self.assertIn(f"## `{name}`\n", page, f"command {name}")
            for action in parser._actions:
                for flag in action.option_strings:
                    if flag.startswith("--") and flag != "--help":
                        self.assertIn(flag, page, f"{name} {flag}")

    def test_every_project_method_is_documented(self):
        page = (DOCS / "python.md").read_text(encoding="utf-8")
        for name in dir(Project):
            if not name.startswith("_"):
                self.assertIn(name, page, f"Project.{name}")


if __name__ == "__main__":
    unittest.main()
