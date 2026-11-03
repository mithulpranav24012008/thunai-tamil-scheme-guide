"""The planner ending without its Answer. Runs the real Strands graph with a scripted model, so no AWS.

In the 2026-11-04 measure run 15 of 40 answers came back "please rephrase". The logs showed the critic passing
the planner's text and then no structured answer, with no error. Strands does exactly that when the model stops
for a reason other than end_turn or tool_use (a content filter, for example).

    python -m unittest discover tests
"""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from strands.models import Model

from agent import app, tools

GOOD = {"language": "en", "answer": "Here are scholarships.", "schemes": [], "follow_up_question": "",
        "steps": ["Apply on the NSP portal"], "escalation": "Ask the school office.", "citations": ["S-PREMSC"]}


def tool(name, inp, n=1):
    return [{"messageStart": {"role": "assistant"}},
            {"contentBlockStart": {"start": {"toolUse": {"toolUseId": f"{name}-{n}", "name": name}}}},
            {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(inp)}}}},
            {"contentBlockStop": {}}, {"messageStop": {"stopReason": "tool_use"}}]


def text(t, stop="end_turn"):
    return [{"messageStart": {"role": "assistant"}}, {"contentBlockDelta": {"delta": {"text": t}}},
            {"contentBlockStop": {}}, {"messageStop": {"stopReason": stop}}]


class Scripted(Model):
    """Plays back one scripted reply per model call: the planner's in order, the critic always passes."""
    _supports_structured_output = True

    def __init__(self, planner):
        self.planner = list(planner)

    def update_config(self, **kw):
        pass

    def get_config(self):
        return {}

    async def structured_output(self, *a, **k):
        raise NotImplementedError

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kw):
        if system_prompt.startswith("Reply ok=false"):
            events = tool("Critique", {"ok": True, "problems": []})
        else:
            events = self.planner.pop(0)
        for e in events:
            yield e


def run(planner, message="I'm an SC student in class 10, any scholarships?"):
    model = Scripted(planner)
    log = io.StringIO()
    with mock.patch.object(app, "_model", lambda: model), redirect_stdout(log):
        out = app.run({"text": message})
    return out, log.getvalue()


LOOKUP = tool("lookup_schemes", {"topic": "scholarship SC class 10"})


class PlannerStopsWithoutItsAnswer(unittest.TestCase):
    def test_answers_from_the_schemes_it_looked_up(self):
        for stop in ("content_filtered", "guardrail_intervened", "stop_sequence"):
            with self.subTest(stop):
                out, log = run([LOOKUP, text("Here are some scholarships...", stop)])
                self.assertEqual(out["meta"]["path"], "recovered")
                self.assertEqual(out["meta"]["planner_stop"], stop)
                self.assertEqual(out["plan"]["citations"], ["S-PREMSC", "S-POSTMSC", "S-NSP"])
                self.assertIn(f"planner stopped ({stop})", log)

    def test_recovered_facts_are_the_verified_records(self):
        out, _ = run([LOOKUP, text("...", "content_filtered")])
        by_id = {g["id"]: g for g in tools.guidance()["items"]}
        for s in out["plan"]["schemes"]:
            g = by_id[s["scheme_id"]]
            self.assertEqual((s["name"], s["official_url"], s["last_checked"]),
                             (g["name"], g["official_url"], g["last_checked"]))
        self.assertTrue(all(s.endswith(by_id[i]["official_url"]) for s, i in zip(out["plan"]["steps"], out["plan"]["citations"])))

    def test_tamil_question_gets_tamil_text(self):
        out, _ = run([tool("lookup_schemes", {"topic": "scholarship SC student"}), text("...", "content_filtered")],
                     "நான் SC மாணவன், உதவித்தொகை வேணும்")
        self.assertEqual(out["plan"]["language"], "ta")
        self.assertTrue(tools.has_tamil(out["plan"]["answer"] + out["plan"]["escalation"]))
        self.assertEqual(out["meta"]["path"], "recovered")

    def test_answer_written_as_json_text_is_used(self):
        out, _ = run([LOOKUP, text("```json\n" + json.dumps(GOOD) + "\n```", "content_filtered")])
        self.assertEqual(out["meta"]["path"], "agent")
        self.assertEqual(out["plan"]["answer"], "Here are scholarships.")

    def test_nothing_looked_up_still_asks_to_rephrase(self):
        out, _ = run([text("...", "content_filtered")])
        self.assertEqual(out["meta"]["path"], "fallback")
        self.assertEqual(out["plan"]["answer"], app.SORRY["en"])
        self.assertEqual(out["plan"]["schemes"], [])

    def test_unrelated_lookup_returns_nothing_to_cite(self):
        out, _ = run([tool("lookup_schemes", {"topic": "housing loan"}), text("...", "content_filtered")])
        self.assertEqual(out["meta"]["path"], "fallback")

    def test_normal_answer_is_unchanged(self):
        out, _ = run([LOOKUP, tool("Answer", GOOD, 2)])
        self.assertEqual(out["meta"]["path"], "agent")
        self.assertNotIn("planner_stop", out["meta"])


if __name__ == "__main__":
    unittest.main()
