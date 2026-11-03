"""Tests for the speech→agent pipeline: transcript → run → answer or handoff.

Emergency transcripts trigger the RedFlagGate before any Bedrock call, so those
tests run without mocking.  Non-emergency transcripts mock run() to avoid a
Bedrock dependency.

    python -m unittest discover tests
"""
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from agent.app import _handle_transcript


class TestEmergencyTranscriptHandoff(unittest.TestCase):
    """Spoken emergencies must hand off to 108 — no extra confirmation."""

    def test_tanglish_emergency_handoff(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = _handle_transcript("nenju vali, moochu vida mudiyala", False)
        self.assertEqual(rc, 0)
        output = out.getvalue()
        self.assertIn("You said:", output)
        self.assertIn("108", output)

    def test_tamil_emergency_handoff(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = _handle_transcript("நெஞ்சு வலிக்குது, மூச்சு விட முடியல", False)
        self.assertEqual(rc, 0)
        self.assertIn("You said:", out.getvalue())

    def test_english_emergency_handoff(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = _handle_transcript("chest pain can't breathe", False)
        self.assertEqual(rc, 0)
        self.assertIn("108", out.getvalue())


class TestNormalTranscriptAgent(unittest.TestCase):
    """Non-emergency transcripts go through the agent path (mocked)."""

    @patch("agent.app.run")
    def test_english_scholarship_transcript(self, mock_run):
        mock_run.return_value = {
            "plan": {"language": "en", "answer": "Here are scholarships...",
                      "schemes": [], "follow_up_question": "", "steps": [],
                      "escalation": "", "citations": []},
            "meta": {"path": "agent", "passes": 1, "critic_ok": True},
        }
        out = io.StringIO()
        with redirect_stdout(out):
            rc = _handle_transcript("I'm studying in class 10, any scholarship", False)
        self.assertEqual(rc, 0)
        mock_run.assert_called_once_with({"text": "I'm studying in class 10, any scholarship"})
        self.assertIn("You said:", out.getvalue())

    @patch("agent.app.run")
    def test_tanglish_health_transcript(self, mock_run):
        mock_run.return_value = {
            "plan": {"language": "ta", "answer": "உதவித்தொகை உண்டு...",
                      "schemes": [], "follow_up_question": "", "steps": [],
                      "escalation": "", "citations": []},
            "meta": {"path": "agent", "passes": 1, "critic_ok": True},
        }
        out = io.StringIO()
        with redirect_stdout(out):
            rc = _handle_transcript("enakku health insurance venum", False)
        self.assertEqual(rc, 0)
        mock_run.assert_called_once_with({"text": "enakku health insurance venum"})


class TestLowConfidence(unittest.TestCase):
    """Low-confidence transcripts: plain → ask to repeat; red-flag → handoff."""

    def test_low_confidence_empty_asks_repeat(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = _handle_transcript("", True)
        self.assertEqual(rc, 1)
        self.assertIn("didn't catch", out.getvalue())

    def test_low_confidence_plain_question_asks_repeat(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = _handle_transcript("some unclear audio about school", True)
        self.assertEqual(rc, 1)
        self.assertIn("didn't catch that clearly", out.getvalue())

    def test_low_confidence_redflag_handoff(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = _handle_transcript("chest pain maybe", True)
        self.assertEqual(rc, 0)
        self.assertIn("108", out.getvalue())


if __name__ == "__main__":
    unittest.main()
