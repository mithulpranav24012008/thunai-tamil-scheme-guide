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


def language_of(text):
    return "ta" if TAMIL.search(text or "") else "en"


def has_tamil(text):
    return bool(TAMIL.search(text or ""))


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
    words = [w for w in re.findall(r"\w+", topic.lower()) if len(w) > 2]
    items = guidance()["items"]

    if not words:
        return [_scheme_record(g) for g in items[:6]]

    hits = [g for g in items if any(w in (g["id"] + " " + g["text"]).lower() for w in words)]
    return [_scheme_record(g) for g in (hits or items)[:6]]


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
