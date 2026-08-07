"""Claim Extraction Agent (claim + entities + claim type + search_query)."""

from backend import llm

_CLAIM_PROMPT = """You extract the central factual claim from a user's message
so it can be fact-checked. The user may write in English or Hindi/Hinglish.

USER MESSAGE: "{message}"

Return ONLY a JSON object with this exact shape:
{{
  "claim_text": "the core claim as a clear English statement",
  "entities": {{"people": [], "organizations": [], "places": [], "dates": [], "events": []}},
  "claim_type": "factual | opinion | satire",
  "search_query": "concise web search query to find evidence for this claim"
}}

Guidelines:
- Strip filler ("I heard that", "is it true", "bro") and keep the factual core.
- claim_text must be a neutral statement, not a question.
- search_query should include key names/keywords for good search results."""


def extract_claim(message: str) -> dict:
    prompt = _CLAIM_PROMPT.format(message=(message or "").replace('"', "'"))
    default = {
        "claim_text": message,
        "entities": {"people": [], "organizations": [], "places": [], "dates": [], "events": []},
        "claim_type": "factual",
        "search_query": message,
    }
    result = llm.call_llm_json(prompt, reasoning=False, default=default)
    result.setdefault("claim_text", message)
    result.setdefault("claim_type", "factual")
    result.setdefault("search_query", result.get("claim_text", message))
    ents = result.get("entities") or {}
    
    for k in ("people", "organizations", "places", "dates", "events"):
        ents.setdefault(k, [])
    result["entities"] = ents
    return result
