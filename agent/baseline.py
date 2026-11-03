"""One agent, one prompt, same model and the same guidance: the baseline to beat.

No tools, no graph, no critic, no hook. All scheme records are pasted into the
prompt. The measurement framework runs this on the same cases as the agent.
"""
import time

from strands import Agent

from . import tools
from .app import _model
from .plan import Answer


def run(case):
    t0 = time.time()
    lang = case.get("lang") or tools.language_of(case["text"])
    lines = []
    for g in tools.guidance()["items"]:
        lines.append(f"{g['id']}: {g['name']} ({g['jurisdiction']}). {g['benefit']} "
                     f"Eligibility: {g['eligibility']} URL: {g['official_url']} "
                     f"Source: {g['source_title']} Checked: {g['last_checked']}")
    prompt = (
        "You are Thunai, a friendly scheme-guide assistant for Tamil Nadu and India. "
        "Help the user find relevant government health or education schemes. "
        "Suggest only schemes from the list below — cite the scheme id. "
        "Never invent a scheme, URL, phone number, or eligibility rule. "
        "Do not diagnose or prescribe. For emergencies, tell the user to call 108. "
        f"Answer in {'natural Tamil' if lang == 'ta' else 'English'}. "
        "Keep it concise.\n\nSchemes:\n" + "\n".join(lines)
    )
    a = Agent(model=_model(), callback_handler=None, structured_output_model=Answer, system_prompt=prompt)
    msg = f"User: {case['text']}"
    ans = a(msg).structured_output
    if ans is None:
        # Fail closed: return a safe default instead of crashing
        ans = Answer(
            language=lang,
            answer="I'm sorry, I couldn't process that. Please try rephrasing your question." if lang == "en"
                   else "மன்னிக்கவும், உங்கள் கேள்வியை மறுபடியும் கேளுங்கள்.",
            schemes=[],
            follow_up_question="",
            steps=[],
            escalation="",
            citations=[],
        )
    return {"plan": ans.model_dump(), "meta": {"path": "baseline", "latency_ms": int((time.time() - t0) * 1000)}}
