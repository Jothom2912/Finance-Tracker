"""Focused regression tests for dev-notes retrieval-budget checks."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import notes_check


class RetrievalBudgetTests(unittest.TestCase):
    def test_current_entry_documents_fit_budgets(self) -> None:
        problems: list[str] = []
        notes_check.check_retrieval_budgets(problems)
        self.assertEqual([], problems)

    def test_reports_oversized_status_and_index_hook(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            notes = Path(directory)
            (notes / "STATUS.md").write_text("word\n" * 101, encoding="utf-8")
            long_hook = "- [note](note.md) — " + ("x" * 241)
            (notes / "00-INDEX.md").write_text(long_hook + "\n", encoding="utf-8")
            (notes / "backlog").mkdir()
            (notes / "backlog" / "BACKLOG.md").write_text("", encoding="utf-8")
            problems: list[str] = []

            with patch.object(notes_check, "NOTES", notes):
                notes_check.check_retrieval_budgets(problems)

        self.assertTrue(any("101 lines exceeds 100" in problem for problem in problems))
        self.assertTrue(any("hook is" in problem for problem in problems))


if __name__ == "__main__":
    unittest.main()
