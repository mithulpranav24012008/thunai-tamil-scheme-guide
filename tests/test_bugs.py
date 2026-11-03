"""Regression tests for bugs found in the November 2026 bug hunt. None of them needs AWS.

    python -m unittest discover tests
"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from agent import app, tools
from agent.plan import Answer
from agent.safety import red_flags
from ship_kit import cases as casesmod
from ship_kit import cli, measure, video

lookup = tools.lookup_schemes._tool_func


def fake_graph(seen):
    """Stands in for the Bedrock graph: runs the real RedFlagGate, records what it was given, answers plainly."""
    def build(lang, gate):
        def call(prompt, invocation_state):
            seen.update(prompt=prompt, user_text=invocation_state["user_text"], lang=lang)
            event = SimpleNamespace(invocation_state=invocation_state, cancel_node=None)
            gate._before(event)
            if event.cancel_node:
                raise RuntimeError(event.cancel_node)
            ans = Answer(language=lang, answer="ok", escalation="", citations=[])
            return SimpleNamespace(results={"planner": SimpleNamespace(result=SimpleNamespace(structured_output=ans))},
                                   execution_order=[SimpleNamespace(node_id="planner")])
        return call
    return build


class StudyingIsNotDying(unittest.TestCase):
    def test_studying(self):
        for text in ["I am studying in class 10, any scholarship?", "my son is studying engineering", "studying in college, need a bus pass"]:
            with self.subTest(text):
                self.assertEqual(red_flags(text), [])

    def test_dying_still_caught(self):
        self.assertIn("dying", red_flags("I think I'm dying"))

    def test_scheme_records_do_not_trip_except_the_helpline(self):
        # Thunai's own answers quote these records; only KIRAN's text names suicide, as a helpline should.
        for g in tools.guidance()["items"]:
            blob = " ".join(str(g.get(k, "")) for k in ("name", "benefit", "eligibility", "exclusions"))
            with self.subTest(g["id"]):
                if g["id"] != "S-KIRAN":
                    self.assertEqual(red_flags(blob), [])


class ChatJudgesOnlyTheLatestMessage(unittest.TestCase):
    def run_case(self, case):
        seen = {}
        with mock.patch.object(app, "build_graph", fake_graph(seen)), redirect_stdout(io.StringIO()):
            out = app.run(case)
        return out, seen

    def test_earlier_emergency_does_not_lock_the_chat(self):
        history = [("User", "I have chest pain"), ("Thunai", app.HANDOFF["en"])]
        out, seen = self.run_case({"text": "I'm fine now. Any scholarship for my daughter?", "history": history})
        self.assertEqual(out["meta"]["path"], "agent")
        self.assertEqual(seen["user_text"], "I'm fine now. Any scholarship for my daughter?")

    def test_thunai_naming_a_helpline_does_not_trip_the_gate(self):
        kiran = next(g for g in tools.guidance()["items"] if g["id"] == "S-KIRAN")
        history = [("User", "I feel low, any support?"), ("Thunai", kiran["benefit"] + " " + kiran["eligibility"])]
        out, _ = self.run_case({"text": "Is it free to call?", "history": history})
        self.assertEqual(out["meta"]["path"], "agent")

    def test_emergency_in_latest_message_still_hands_off(self):
        out, _ = self.run_case({"text": "now I can't breathe", "history": [("User", "need a bus pass")]})
        self.assertEqual(out["meta"]["path"], "handoff")

    def test_history_reaches_the_planner(self):
        _, seen = self.run_case({"text": "class 10", "history": [("User", "my son needs a scholarship")]})
        self.assertIn("my son needs a scholarship", seen["prompt"])
        self.assertTrue(seen["prompt"].rstrip().endswith("class 10"))

    def test_language_follows_the_user_not_the_reply(self):
        history = [("User", "எனக்கு உதவி வேணும்"), ("Thunai", "உங்கள் தேவை புரிகிறது.")]
        _, seen = self.run_case({"text": "Actually, please answer in English. I need a bus pass.", "history": history})
        self.assertEqual(seen["lang"], "en")

    def test_the_real_chat_loop(self):
        """Drives chat_loop with typed lines: an emergency, then an ordinary question, then quit."""
        paths, seen = [], {}
        real_run = app.run

        def spy(case):
            out = real_run(case)
            paths.append((case["text"], out["meta"]["path"]))
            return out
        typed = iter(["I have chest pain", "I'm fine now. Any scholarship for my daughter?", "quit"])
        with mock.patch.object(app, "build_graph", fake_graph(seen)), mock.patch.object(app, "run", spy), \
                mock.patch("builtins.input", lambda _: next(typed)), redirect_stdout(io.StringIO()):
            app.chat_loop()
        self.assertEqual([p for _, p in paths], ["handoff", "agent"])
        self.assertEqual(paths[1][0], "I'm fine now. Any scholarship for my daughter?")

    def test_short_reply_keeps_the_conversation_language(self):
        history = [("User", "எனக்கு உதவித்தொகை வேணும்"), ("Thunai", "நீங்கள் எந்த வகுப்பில் படிக்கிறீர்கள்?")]
        _, seen = self.run_case({"text": "10th", "history": history})
        self.assertEqual(seen["lang"], "ta")


class LookupRanksByRelevance(unittest.TestCase):
    def ids(self, topic):
        return [r["id"] for r in lookup(topic)]

    def test_best_match_first(self):
        self.assertEqual(self.ids("free bus pass for college")[0], "S-TNBUS")
        self.assertEqual(set(self.ids("mental health support")[:2]), {"S-KIRAN", "S-TELEMANAS"})
        self.assertEqual(set(self.ids("health insurance hospital")[:2]), {"S-PMJAY", "S-CMCHIS"})
        self.assertEqual(self.ids("maternity benefit for pregnant women")[0], "S-MRMS")
        self.assertEqual(self.ids("disability pension")[0], "S-IGNDPS")
        self.assertIn("S-PREMSC", self.ids("scholarship for SC student in class 10")[:3])

    def test_nothing_relevant_returns_nothing(self):
        self.assertEqual(self.ids("housing loan for a new house"), [])

    def test_never_more_than_six(self):
        self.assertLessEqual(len(self.ids("health education scholarship insurance pension support")), 6)


class KitCommandsFitThunai(unittest.TestCase):
    def test_cases_show_does_not_crash(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(["cases", "show"])
        self.assertEqual(code, 0)
        self.assertIn("thunai-01", buf.getvalue())

    def test_measure_table_uses_the_project_title(self):
        rows = {"cases": 1, "emergency_recall": 1.0, "emergency_cases": 1, "unsafe": 0, "unsafe_rate": 0, "threshold_accuracy": 1.0,
                "completeness": 1.0, "citation_faithfulness": 1.0, "goal_success": 1.0, "latency_p50_ms": 1, "errors": 0,
                "critic_passed": 1.0, "failed_closed": 0}
        part = {"overall": rows, "by_language": {}, "by_job": {}, "rows": []}
        md = measure.markdown({"when": "now", "model": "m", "cases": {"emergency": 1, "ta": 1, "jobs": 1}, "agent": part,
                               "baseline": part, "gate": {}, "labels": {}, "title": "Thunai — Tamil Scheme Guide"})
        self.assertIn("| Metric | Thunai — Tamil Scheme Guide |", md)
        self.assertNotIn("HeatSafe", md)

    def test_video_badge_for_a_handoff(self):
        kind, big, _ = video._badge("safety", "RED FLAG (chest pain, can't breathe) -> HAND OFF, agents cancelled")
        self.assertEqual((kind, big), ("stop", "CALL 108"))


if __name__ == "__main__":
    unittest.main()
