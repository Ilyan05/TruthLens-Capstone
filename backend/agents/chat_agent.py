from backend import llm

_C = """
You are TruthLens, a professional AI fact-checking assistant. Reply briefly (1-3 sentences).
If asked what you can do, say you verify text/audio/image claims and return a verdict
(Real/Fake/Misleading/Manipulated/Inconclusive) with evidence.
User may write Hindi/English; reply English.
CONVERSATION:
{history}

USER: "{message}"
TruthLens:
"""

_F = """
You are TruthLens.
Answer this follow-up using ONLY the previous result + evidence.
Do NOT invent facts.
PREVIOUS VERDICT: {verdict} (confidence {confidence})
SUMMARY: {summary}
EVIDENCE:
{evidence}

USER FOLLOW-UP: "{message}"
TruthLens:
"""

def _hist(h, limit=6):
    L = []

    for m in (h or [])[-limit:]:
        L.append(
            ("USER" if m.get("role") == "user" else "TruthLens")
            + ": "
            + m.get("content", "")
        )

    return "\n".join(L) if L else "(no prior messages)"

def casual_reply(message, history):
    p = _C.format(
        history=_hist(history),
        message=(message or "").replace('"', "'")
    )

    try:
        return llm.call_llm(p, reasoning=False).strip()

    except Exception:
        return "Hi! I'm TruthLens. Share any claim and I'll verify it with evidence."

def follow_up_reply(message, last_verdict):
    lv = last_verdict or {}

    ev = (
        "\n".join(
            f"- {e.get('title', '')} ({e.get('source_type', '')}): "
            f"{e.get('snippet', '')}"
            for e in (lv.get("evidence") or [])[:5]
        )
        or "(no evidence stored)"
    )

    p = _F.format(
        verdict=lv.get("verdict", "Inconclusive"),
        confidence=round(lv.get("confidence", 0.0), 2),
        summary=lv.get("summary", ""),
        evidence=ev,
        message=(message or "").replace('"', "'")
    )

    try:
        return llm.call_llm(p, reasoning=False).strip()

    except Exception:
        return (
            f"Based on the previous check, "
            f"the verdict was {lv.get('verdict', 'Inconclusive')}."
        )