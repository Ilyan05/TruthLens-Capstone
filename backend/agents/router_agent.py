from backend import llm

_P = """
Intent router of a fact-checking assistant.

Classify USER MESSAGE:

- "claim": a factual statement or request to verify.
- "chat": greetings, thanks, small talk, questions about how you work.
- "follow_up": a question about the PREVIOUS fact-check result.

If HAS_PREVIOUS_VERDICT is false, only pick claim or chat.
User may write Hindi/English.
HAS_PREVIOUS_VERDICT: {has_prev}
USER MESSAGE: "{message}"
Respond ONLY JSON:
{{"intent":"claim|chat|follow_up","reason":"short"}}
"""

def route(message, has_previous_verdict):
    msg = (message or "").strip()

    if not msg:
        return {
            "intent": "chat",
            "reason": "empty"
        }

    p = _P.format(
        has_prev=str(bool(has_previous_verdict)).lower(),
        message=msg.replace('"', "'")
    )

    r = llm.call_llm_json(
        p,
        reasoning=False,
        default={
            "intent": "claim",
            "reason": "fallback"
        }
    )

    it = r.get("intent", "claim")

    if it == "follow_up" and not has_previous_verdict:
        it = "claim"

    if it not in ("claim", "chat", "follow_up"):
        it = "claim"

    return {
        "intent": it,
        "reason": r.get("reason", "")
    }