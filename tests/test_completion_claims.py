#!/usr/bin/env python3
"""Unit tests for completion-claim detection in fabrication_detector.

Port of original test suite from Alena Zakharova's personal hooks.
"""
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
os.environ["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from fabrication_detector import find_completion_claims, has_evidence  # noqa: E402


class TestCompletionClaims(unittest.TestCase):
    def setUp(self):
        self.phrases = ["done", "работает", "готово", "deployed", "added"]

    def test_simple_claim(self):
        self.assertTrue(find_completion_claims("All done.", self.phrases))

    def test_negation_filter_ru(self):
        # "не " triggers negation filter
        self.assertFalse(find_completion_claims("не готово пока.", self.phrases))

    def test_question_filter(self):
        # "?" triggers negation/question filter
        self.assertFalse(find_completion_claims("is it done?", self.phrases))

    def test_code_block_stripped(self):
        text = "```\nall done\n```\nno claim here."
        self.assertFalse(find_completion_claims(text, self.phrases))

    def test_inline_code_stripped(self):
        text = "I left `done` in the code but no claim."
        self.assertFalse(find_completion_claims(text, self.phrases))

    def test_blockquote_stripped(self):
        text = "> user said all done\nmy response has no claim."
        self.assertFalse(find_completion_claims(text, self.phrases))

    def test_ru_claim(self):
        self.assertTrue(find_completion_claims("Всё работает отлично.", self.phrases))

    def test_multiple_phrases_one_sentence(self):
        # Only one flag per sentence (inner break)
        r = find_completion_claims("File added and deployed.", self.phrases)
        self.assertEqual(len(r), 1)

    def test_empty_phrases(self):
        self.assertEqual(find_completion_claims("done done done", []), [])

    def test_empty_text(self):
        self.assertEqual(find_completion_claims("", self.phrases), [])

    def test_evidence_present(self):
        self.assertTrue(has_evidence(["Read", "Edit"]))
        self.assertTrue(has_evidence(["Bash"]))
        self.assertTrue(has_evidence(["Grep", "Edit", "Write"]))

    def test_evidence_absent(self):
        self.assertFalse(has_evidence([]))
        self.assertFalse(has_evidence(["Edit"]))
        self.assertFalse(has_evidence(["Write", "TaskCreate"]))

    def test_evidence_mcp_read(self):
        self.assertTrue(has_evidence(["mcp__exa__web_search_exa"]))
        self.assertTrue(has_evidence(["mcp__supabase__execute_sql"]))


if __name__ == "__main__":
    unittest.main()
