from backend import llm, config

_PREGROUND_PROMPT = """You are the pre-grounding step of a fact-checker.
Using ONLY your own knowledge (no web search yet), assess this claim.

CLAIM: "{claim}"

Return ONLY a JSON object:
{{
  "initial_assessment": "likely_true | likely_false | unclear",
  "initial_confidence": 0.0,
  "risk_level": "low | high",
  "risk_topic": "none | politics | election | health | legal | religion | violence | finance | person_allegation",
  "reason": "one short sentence"
}}

Rules:
- "high" if the claim involves politics, elections, health/medical advice,
  legal guilt, religion, violence, finance, or a serious allegation about a
  named person. Otherwise "low".
- initial_confidence is 0.0-1.0. Be conservative: if unsure, use "unclear"."""


def pre_ground(claim_text: str) -> dict:
    prompt = _PREGROUND_PROMPT.format(claim=(claim_text or "").replace('"', "'"))
    default = {
        "initial_assessment": "unclear", "initial_confidence": 0.0,
        "risk_level": "high", "risk_topic": "none", "reason": "fallback",
    }
    result = llm.call_llm_json(prompt, reasoning=True, default=default)
    try:
        conf = float(result.get("initial_confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    result["initial_confidence"] = max(0.0, min(1.0, conf))
    result.setdefault("initial_assessment", "unclear")
    result.setdefault("risk_level", "high")
    result["fast_path"] = (
        result["initial_confidence"] >= config.FASTPATH_CONFIDENCE
        and result.get("risk_level") == "low"
    )
    return result
