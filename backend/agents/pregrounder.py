from backend import llm, config

_P = """
Pre-grounding step.

Using ONLY your knowledge (no search yet), assess:

CLAIM: "{claim}"

Return ONLY JSON:

{{
    "initial_assessment": "likely_true | likely_false | unclear",
    "initial_confidence": 0.0,
    "risk_level": "low | high",
    "risk_topic": "none | politics | election | health | legal | religion | violence | finance | person_allegation",
    "reason": "one short sentence"
}}

"high" if politics/elections/health/legal/religion/violence/finance/allegation.
Else "low".
"""


def pre_ground(claim_text):
    p = _P.format(
        claim=(claim_text or "").replace('"', "'")
    )

    d = {
        "initial_assessment": "unclear",
        "initial_confidence": 0.0,
        "risk_level": "high",
        "risk_topic": "none",
        "reason": "fallback"
    }

    r = llm.call_llm_json(
        p,
        reasoning=True,
        default=d
    )

    try:
        c = float(r.get("initial_confidence", 0.0))
    except (TypeError, ValueError):
        c = 0.0

    r["initial_confidence"] = max(0.0,min(1.0, c))
        
    r.setdefault("initial_assessment","unclear")
    r.setdefault("risk_level","high")

    r["fast_path"] = (
        r["initial_confidence"] >= config.FASTPATH_CONFIDENCE
        and r.get("risk_level") == "low"
    )
    return r