"""Structured output for Thunai — Tamil Scheme Guide.

SchemeRecommendation holds every field the user must see for each scheme.
Answer holds the conversational response, the scheme list, and a single
follow-up question when the agent needs more detail to narrow results.
"""
from typing import Literal

from pydantic import BaseModel, Field


class SchemeRecommendation(BaseModel):
    scheme_id: str = Field(description="The scheme id from lookup_schemes, e.g. S-PMJAY")
    name: str = Field(description="Official scheme name, kept exactly as in the source")
    jurisdiction: str = Field(description="Central, Tamil Nadu, or Other state")
    benefit: str = Field(description="What the scheme provides, in plain language in the user's language")
    eligibility: str = Field(description="Who may be eligible, in the user's language")
    uncertainties: str = Field(description="Exclusions or details that must be verified, in the user's language")
    documents: list[str] = Field(default_factory=list, description="Likely documents needed, in the user's language")
    application_steps: list[str] = Field(default_factory=list, description="Next practical steps, in the user's language")
    official_url: str = Field(description="Official application or information link")
    source_title: str = Field(description="Official source title")
    last_checked: str = Field(description="Date the information was last checked, ISO format")


class Answer(BaseModel):
    language: Literal["en", "ta"]
    answer: str = Field(description="The main response in the user's language: greeting, what was understood, and a brief summary")
    schemes: list[SchemeRecommendation] = Field(default_factory=list, description="Recommended schemes with full details")
    follow_up_question: str = Field(default="", description="One follow-up question to narrow eligibility, or empty if none needed. Explain why sensitive details are needed before asking.")
    steps: list[str] = Field(default_factory=list, description="What to do next, short steps")
    escalation: str = Field(description="When and who to ask for human help")
    citations: list[str] = Field(description="Scheme ids returned by lookup_schemes that were used")


class Critique(BaseModel):
    ok: bool
    problems: list[str] = Field(default_factory=list)
