"""Thunai — Tamil Scheme Guide.

A Strands Agents SDK agent that helps people in Tamil Nadu and India discover
health, medical-support, and education schemes. Speaks natural Tamil and English.

    python -m agent.app "your message"            # one-shot answer
    python -m agent.app "message" --json          # JSON output
    python -m agent.app --chat                     # interactive conversation
    python -m agent.app --audio file.wav           # transcribe and answer
    python -m agent.app --chat --voice             # voice chat (microphone)

Architecture: planner -> critic graph with a red-flag hook and code-level fact
enforcement. The planner calls lookup_schemes and structures the answer; the
critic checks language, citations, and unsupported claims; a hook cancels both
agents the moment a medical emergency is detected.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

from strands import Agent
from strands.hooks import BeforeNodeCallEvent, HookProvider, HookRegistry
from strands.models import BedrockModel
from strands.multiagent import GraphBuilder

from . import tools
from . import speech
from .safety import red_flags
from .plan import Answer, Critique, SchemeRecommendation

MODEL_ID = os.environ.get("SHIP_MODEL", "us.amazon.nova-2-lite-v1:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")
logging.getLogger("strands").setLevel(logging.CRITICAL)

# ── GOAL ────────────────────────────────────────────────────────────────────
GOAL = (
    "You are Thunai, a friendly scheme-guide assistant for people in Tamil Nadu and India. "
    "You help people discover government health and education schemes that may fit their needs. "
    "Respond in {lang} (en = English, ta = natural Tamil script). "
    "Speak in fluent, natural, friendly Tamil when the user speaks Tamil — use everyday wording, "
    "not stiff bureaucratic Tamil. Support natural Tamil-English code-switching when the user does. "
    "Keep official scheme names and links exactly as returned by the tool.\n\n"
    "Rules:\n"
    "1. Call lookup_schemes first with English keywords that match the user's need.\n"
    "2. Cite only the scheme ids the tool returns. Never invent a scheme, benefit amount, "
    "eligibility rule, deadline, contact number, or application link.\n"
    "3. For each relevant scheme, include all fields from the tool output in the schemes list.\n"
    "4. If you need more information to narrow results, ask ONE follow-up question. "
    "Explain why you need sensitive details (like income bracket or caste category) before asking, "
    "and let the user skip any question.\n"
    "5. Never request Aadhaar numbers, OTPs, passwords, bank details, or full medical records.\n"
    "6. If you cannot verify a detail, say so plainly and direct the user to the official source.\n"
    "7. Do not guarantee eligibility or approval. Present results as schemes worth checking.\n"
    "8. Do not diagnose, prescribe, or recommend changing treatment. For medical questions, give "
    "only general, cautious information and encourage a qualified clinician.\n"
    "9. Keep responses clear and concise. Short sentences."
)
PLANNER = GOAL + (
    "\n\nProduce the Answer with: a brief greeting and summary in 'answer', the matching "
    "schemes in 'schemes' (with all fields), one follow-up question in 'follow_up_question' "
    "(or empty if you have enough to answer), practical next steps in 'steps', and a brief "
    "escalation note in 'escalation'. Set citations to the scheme ids you used."
)

CRITIC = (
    "Reply ok=false with one line per problem if the answer: is not in {lang}, cites a scheme id "
    "not in {ids}, gives a benefit or eligibility rule not supported by the scheme records, "
    "fabricates a URL or phone number, is empty, or asks for Aadhaar/OTP/password/bank details. "
    "Otherwise ok=true."
)

# ── SAFETY: what must stop the agents and hand off to a human ──────────────
# Code owns this — the model cannot change it. The patterns, in Tamil script, Tanglish and English,
# live in agent/safety.py and are tested in tests/test_safety.py.
HANDOFF = {
    "en": (
        "This sounds like a medical emergency or a question about diagnosis or treatment. "
        "I cannot help with that. Please call 108 for an ambulance right now, or go to the nearest "
        "hospital. For mental health support, call KIRAN at 1800-599-0199 (free, 24/7) or "
        "Tele-MANAS at 14416."
    ),
    "ta": (
        "இது ஒரு மருத்துவ அவசரநிலை அல்லது நோய் கண்டறிதல் கேள்வி போல் தெரிகிறது. "
        "நான் இதில் உதவ முடியாது. உடனே 108 அழைத்து ஆம்புலன்ஸ் வரவழைக்கவும் "
        "அல்லது அருகிலுள்ள மருத்துவமனைக்குச் செல்லவும். "
        "மனநல ஆதரவுக்கு KIRAN 1800-599-0199 (இலவசம், நாள் முழுவதும்) "
        "அல்லது Tele-MANAS 14416 என்ற எண்ணில் அழைக்கவும்."
    ),
}


class RedFlagGate(HookProvider):
    """Cancels the planner the moment the user text shows a danger (see agent/safety.py)."""

    def __init__(self):
        self.tripped = []

    def register_hooks(self, registry: HookRegistry, **_):
        registry.add_callback(BeforeNodeCallEvent, self._before)

    def _before(self, event: BeforeNodeCallEvent):
        hits = red_flags(event.invocation_state.get("user_text", ""))
        if hits:
            self.tripped = hits
            event.cancel_node = "red flag: " + ", ".join(hits)


def _model():
    return BedrockModel(model_id=MODEL_ID, region_name=REGION, temperature=0.2)


def build_graph(lang, gate):
    planner = Agent(
        model=_model(),
        name="planner",
        system_prompt=PLANNER.format(lang=lang),
        tools=[tools.lookup_schemes],
        structured_output_model=Answer,
        callback_handler=None,
    )
    critic = Agent(
        model=_model(),
        name="critic",
        system_prompt=CRITIC.format(lang=lang, ids=sorted(tools.guidance_ids())),
        structured_output_model=Critique,
        callback_handler=None,
    )

    def again(state):
        r = state.results.get("critic")
        v = getattr(r.result, "structured_output", None) if r else None
        n = sum(1 for x in state.execution_order if x.node_id == "planner")
        if v is not None:
            print(f"[critic] pass {n}: " + ("PASS" if v.ok else "REVISE - " + "; ".join(v.problems)[:200]), flush=True)
        return bool(v is not None and not v.ok and n < 2)

    b = GraphBuilder()
    b.add_node(planner, "planner")
    b.add_node(critic, "critic")
    b.add_edge("planner", "critic")
    b.add_edge("critic", "planner", condition=again)
    b.set_entry_point("planner")
    b.set_max_node_executions(4)
    b.reset_on_revisit(True)
    b.set_hook_providers([gate])
    return b.build()


# ── Code owns the facts that must never be wrong ─────────────────────────────
def _enforce(ans: Answer) -> tuple[Answer, list[str]]:
    """Replace any scheme URL, name, or detail the model changed with the correct value
    from the curated dataset. Returns the corrected answer and a list of what was fixed."""
    fixes = []
    by_id = {g["id"]: g for g in tools.guidance()["items"]}
    corrected_schemes = []
    for s in ans.schemes:
        g = by_id.get(s.scheme_id)
        if g is None:
            # Drop schemes not in the dataset — the model invented it
            fixes.append(f"dropped invented scheme '{s.scheme_id}'")
            continue
        if s.official_url != g["official_url"]:
            fixes.append(f"corrected URL for {s.scheme_id}: {s.official_url} -> {g['official_url']}")
            s.official_url = g["official_url"]
        if s.name != g["name"]:
            fixes.append(f"corrected name for {s.scheme_id}")
            s.name = g["name"]
        if s.jurisdiction != g["jurisdiction"]:
            fixes.append(f"corrected jurisdiction for {s.scheme_id}")
            s.jurisdiction = g["jurisdiction"]
        if s.last_checked != g["last_checked"]:
            fixes.append(f"corrected last_checked for {s.scheme_id}")
            s.last_checked = g["last_checked"]
        if s.source_title != g["source_title"]:
            fixes.append(f"corrected source_title for {s.scheme_id}")
            s.source_title = g["source_title"]
        corrected_schemes.append(s)
    ans.schemes = corrected_schemes
    # Remove invalid citations
    valid_ids = tools.guidance_ids()
    clean_cites = [c for c in ans.citations if c in valid_ids]
    if len(clean_cites) != len(ans.citations):
        fixes.append(f"removed {len(ans.citations) - len(clean_cites)} invalid citation(s)")
        ans.citations = clean_cites
    return ans, fixes


def _language(text: str, history: list) -> str:
    """The language of the latest message. A short reply with no Tamil in it ("10th", "yes", "SC")
    says nothing about language, so it keeps the language of the user's previous message."""
    lang = tools.language_of(text)
    if lang == "en" and len(text.split()) <= 3:
        earlier = [said for who, said in history if who == "User"]
        if earlier:
            return tools.language_of(earlier[-1])
    return lang


def _prompt(lang: str, text: str, history: list) -> str:
    if not history:
        return f"User ({lang}): {text}"
    said = "\n".join(f"{who}: {line}" for who, line in history)
    return f"Conversation so far, for context:\n{said}\n\nUser ({lang}): {text}"


def run(case: dict) -> dict:
    """Answer one message. case["history"] holds the earlier turns as (who, text) pairs: they give the
    planner context, but only the latest message is checked for danger and decides the language, so
    Thunai's own replies (which may name a suicide helpline) and an emergency already handed off
    cannot trip the gate again on every later turn."""
    t0 = time.time()
    text, history = case["text"], case.get("history") or []
    lang = case.get("lang") or _language(text, history)
    gate = RedFlagGate()
    meta = {"path": "agent", "passes": 0, "critic_ok": None}
    try:
        res = build_graph(lang, gate)(_prompt(lang, text, history), invocation_state={"user_text": text})
    except RuntimeError:
        if not gate.tripped:
            raise
        res = None
    if gate.tripped:
        print(f"[safety] RED FLAG ({', '.join(gate.tripped)}) -> HAND OFF, agents cancelled", flush=True)
        ans = Answer(
            language=lang,
            answer=HANDOFF[lang],
            schemes=[],
            follow_up_question="",
            steps=[HANDOFF[lang]],
            escalation=HANDOFF[lang],
            citations=[],
        )
        meta["path"] = "handoff"
    else:
        ans = res.results["planner"].result.structured_output
        if ans is None:
            raise RuntimeError("planner returned no structured answer")
        meta["passes"] = sum(1 for n in res.execution_order if n.node_id == "planner")
        critic_result = res.results.get("critic")
        critic_output = getattr(critic_result.result, "structured_output", None) if critic_result else None
        meta["critic_ok"] = critic_output.ok if critic_output else None
    # Code puts the facts back if the model changed them
    ans, fixes = _enforce(ans)
    if fixes:
        print(f"[code] corrected: {'; '.join(fixes)}", flush=True)
    meta["latency_ms"] = int((time.time() - t0) * 1000)
    print(f"[plan] {meta['path']} | {meta['passes']} passes | {meta['latency_ms']} ms", flush=True)
    return {"plan": ans.model_dump(), "meta": meta}


# ── Interactive conversation ───────────────────────────────────────────────────
def _print_answer(ans: dict):
    """Pretty-print an Answer dict for the chat loop."""
    lang_tag = "துணை" if ans.get("language") == "ta" else "Thunai"
    print(f"\n{lang_tag}: {ans.get('answer', '')}\n")
    for s in ans.get("schemes", []):
        print(f"  ── {s.get('name', '?')} ({s.get('jurisdiction', '?')})")
        print(f"     பயன் / Benefit: {s.get('benefit', '')}")
        print(f"     தகுதி / Eligibility: {s.get('eligibility', '')}")
        if s.get("uncertainties"):
            print(f"     ⚠ Verify: {s.get('uncertainties', '')}")
        if s.get("documents"):
            print(f"     Documents: {', '.join(s.get('documents', []))}")
        if s.get("application_steps"):
            print(f"     Steps: {'; '.join(s.get('application_steps', []))}")
        print(f"     Link: {s.get('official_url', '')}")
        print(f"     Source: {s.get('source_title', '')} (checked {s.get('last_checked', '')})")
        print()
    if ans.get("follow_up_question"):
        print(f"  ❓ {ans['follow_up_question']}\n")
    if ans.get("steps"):
        print("  Next steps:")
        for step in ans["steps"]:
            print(f"    • {step}")
        print()
    if ans.get("escalation"):
        print(f"  ⚠ {ans['escalation']}\n")


def _handle_transcript(transcript: str, is_low: bool, json_output: bool = False) -> int:
    """Print transcript, apply low-confidence rule, run agent, print answer."""
    if not transcript:
        print("\nI didn't catch that. Could you repeat or type your question?\n")
        return 1
    print(f"\nYou said: {transcript}\n")
    if is_low:
        if not red_flags(transcript):
            print("I didn't catch that clearly. Could you repeat or type your question?\n")
            return 1
        print("[safety] Low-confidence transcript contains red-flag words — proceeding with handoff\n")
    out = run({"text": transcript})
    if json_output:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        _print_answer(out["plan"])
    return 0


def chat_loop(voice: bool = False, stt_lang: str = "ta-IN"):
    """Interactive conversation: gather details one question at a time, then suggest schemes."""
    print("═" * 60)
    print("  துணை — Tamil Scheme Guide  /  Thunai")
    if voice:
        print("  🎤 Voice mode — speak your question")
    print("  வணக்கம்! Health மற்றும் education schemes பற்றி")
    print("  கேளுங்கள். / Hello! Ask me about health or")
    print("  education schemes in Tamil Nadu and India.")
    print("  Type 'quit' to exit.")
    print("═" * 60 + "\n")

    history: list[tuple[str, str]] = []  # (who, text), the last few turns
    while True:
        if voice:
            try:
                audio_path = speech.record_microphone()
            except Exception as e:
                print(f"\n🎤 Error: {e}\n")
                break
            try:
                result = speech.transcribe_file(audio_path, stt_lang)
            except Exception as e:
                print(f"\nTranscription error: {e}\n")
                continue
            finally:
                speech.cleanup(audio_path)
            user_input = result.get("transcript", "")
            is_low = result.get("is_low_confidence", False)
            if not user_input:
                print("\nI didn't catch that. Could you repeat or type your question?\n")
                continue
            print(f"\nYou said: {user_input}\n")
            if is_low:
                if not red_flags(user_input):
                    print("I didn't catch that clearly. Could you repeat or type your question?\n")
                    continue
                print("[safety] Low-confidence transcript contains red-flag words — proceeding with handoff\n")
        else:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user_input:
                continue
        if user_input.lower() in ("quit", "exit", "வெளியேறு", "முடி"):
            break

        try:
            out = run({"text": user_input, "history": history[-8:]})
        except Exception as e:
            print(f"\nThunai: Sorry, something went wrong: {e}\n")
            continue
        _print_answer(out["plan"])
        history += [("User", user_input), ("Thunai", out["plan"].get("answer", ""))]

    print("\nநன்றி! / Thank you for using Thunai!\n")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m agent.app", description="Thunai — Tamil Scheme Guide")
    ap.add_argument("text", nargs="?", default=None, help="Your question about health or education schemes")
    ap.add_argument("--json", action="store_true", help="Output as JSON")
    ap.add_argument("--chat", action="store_true", help="Interactive conversation mode")
    ap.add_argument("--voice", action="store_true", help="Speak your question (record from microphone)")
    ap.add_argument("--audio", default=None, help="Transcribe an audio file and answer (testable path)")
    ap.add_argument("--stt-lang", default="ta-IN", help="Transcribe language code: ta-IN (Tamil) or en-IN (English)")
    a = ap.parse_args(argv)

    if a.chat:
        return chat_loop(voice=a.voice, stt_lang=a.stt_lang)

    if a.audio:
        try:
            result = speech.transcribe_file(a.audio, a.stt_lang)
        except Exception as e:
            print(f"Transcription error: {e}")
            return 1
        return _handle_transcript(result.get("transcript", ""), result.get("is_low_confidence", False), a.json)

    if not a.text:
        ap.print_help()
        return 1

    out = run({"text": a.text})
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        _print_answer(out["plan"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
