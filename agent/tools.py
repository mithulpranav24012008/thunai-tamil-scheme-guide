"""Thunai tools. Read-only, curated sources only — the agent may cite only these schemes."""
import json
import re
from functools import lru_cache
from pathlib import Path

from strands import tool

DATA = Path(__file__).parent / "data"
TAMIL = re.compile(r"[\u0B80-\u0BFF]")


@lru_cache(maxsize=1)
def guidance():
    return json.loads((DATA / "guidance.json").read_text(encoding="utf-8"))


def guidance_ids():
    return {g["id"] for g in guidance()["items"]}


# Everyday Tamil words as people type them in English letters (Tanglish). One is enough: none of them
# is an English word, and names that are also English-text words (Amma, Anna, Madurai) are left out.
TANGLISH = re.compile(
    r"\b(enakku|enaku|venum|vendum|venam|irukka|iruka|irukku|iruku|illa|illai|illaya|mudiyala|mudiyalai|mudiyuma"
    r"|romba|konjam|pannunga|pannanum|panna|eppadi|epdi|ennaku|sollunga|padikka|padikanum|edukanum|edukkanum"
    r"|nenju|moochu|saaganum|mathirai|maathirai|thookka|mayangi|mayakkam|paambu|kadichiduchu|thonuthu|thonudhu"
    r"|vaanguthu|vanguthu|sethuralam|ungalukku|engalukku|naanga|neenga|kudunga|theriyala|theriyum|kidaikkuma|kidaikum)\b",
    re.IGNORECASE,
)


def language_of(text):
    """'ta' for Tamil script or Tanglish, so the answer comes back in Tamil; otherwise 'en'."""
    text = text or ""
    return "ta" if TAMIL.search(text) or TANGLISH.search(text) else "en"


def has_tamil(text):
    return bool(TAMIL.search(text or ""))


# Words that say nothing about which scheme fits: every scheme record contains them, or they are filler.
STOPWORDS = {
    "the", "and", "for", "with", "any", "are", "from", "that", "this", "have", "has", "who", "what", "how", "can",
    "get", "need", "needs", "want", "help", "about", "into", "our", "your", "their", "there", "some", "also",
    "scheme", "schemes", "government", "govt", "india", "indian",
}


@tool
def lookup_schemes(topic: str) -> list[dict]:
    """Find verified government schemes matching the user's need. Returns full scheme records
    with name, jurisdiction, benefit, eligibility, uncertainties, documents, application steps,
    official URL, source title, and last-checked date. The agent may cite only the ids returned here.

    Args:
        topic: Keywords describing what the user needs, e.g. "health insurance hospital",
               "scholarship school student", "maternity pregnancy", "disability pension",
               "mental health support". Use English keywords even if the user spoke Tamil.
    """
    words = {w for w in re.findall(r"\w+", topic.lower()) if len(w) > 2 and w not in STOPWORDS}
    items = guidance()["items"]

    if not words:
        return [_scheme_record(g) for g in items[:6]]

    # Rank by how many of the keywords each scheme mentions, best first; ties keep the dataset's order.
    # A scheme that matches none is left out, so an unrelated need gets no schemes rather than six random ones.
    def score(g):
        text = (g["id"] + " " + g["name"] + " " + g["text"]).lower()
        return sum(1 for w in words if w in text)

    ranked = sorted(((score(g), i, g) for i, g in enumerate(items)), key=lambda x: (-x[0], x[1]))
    return [_scheme_record(g) for s, _, g in ranked if s > 0][:6]


def _scheme_record(g: dict) -> dict:
    """Return a full scheme record for the planner to cite."""
    return {
        "id": g["id"],
        "name": g["name"],
        "jurisdiction": g["jurisdiction"],
        "benefit": g["benefit"],
        "eligibility": g["eligibility"],
        "uncertainties": g["exclusions"],
        "documents": g["documents"],
        "application_steps": g["application_steps"],
        "official_url": g["official_url"],
        "source_title": g["source_title"],
        "last_checked": g["last_checked"],
    }
