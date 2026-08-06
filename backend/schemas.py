"""TruthLens - Pydantic Schemas."""
from pydantic import BaseModel
from typing import List


class Evidence(BaseModel):
    title: str = ""
    url: str = ""
    source_type: str = "web"          # factcheck | news | official | encyclopedia | web
    snippet: str = ""
    stance: str = "neutral"           # supporting | contradicting | neutral


class ClaimObject(BaseModel):
    claim_text: str = ""
    entities: dict = {}
    claim_type: str = "factual"
    search_query: str = ""


class VerdictObject(BaseModel):
    verdict: str = "Inconclusive"
    confidence: float = 0.0
    summary: str = ""
    evidence: List[Evidence] = []
    reasoning: dict = {}
    needs_human_review: bool = False
