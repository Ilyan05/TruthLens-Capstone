from backend import llm

_P = """
Extract the central factual claim so it can be fact-checked.
User may write Hindi/English.
USER MESSAGE: "{message}"
Return ONLY JSON:

{{
    "claim_text": "clear English statement",
    "entities": {{
        "people": [],
        "organizations": [],
        "places": [],
        "dates": [],
        "events": []
    }},
    "claim_type": "factual | opinion | satire",
    "search_query": "concise web search query"
}}
"""

def extract_claim(message):
    p = _P.format(
        message=(message or "").replace('"', "'")
    )

    d = {
        "claim_text": message,
        "entities": {
            "people": [],
            "organizations": [],
            "places": [],
            "dates": [],
            "events": []
        },
        "claim_type": "factual",
        "search_query": message
    }

    r = llm.call_llm_json(
        p,
        reasoning=False,
        default=d
    )

    r.setdefault("claim_text", message)
    r.setdefault("claim_type", "factual")
    r.setdefault(
        "search_query",
        r.get("claim_text", message)
    )

    e = r.get("entities") or {}

    for k in (
        "people",
        "organizations",
        "places",
        "dates",
        "events"
    ):
        e.setdefault(k, [])
    r["entities"] = e
    return r