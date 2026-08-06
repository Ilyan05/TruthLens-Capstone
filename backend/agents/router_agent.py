"""Intent Router — claim | chat | follow_up (rule-then-LLM)."""
from backend import llm

_ROUTER_PROMPT = """You are the intent router of a fact-checking assistant.
Classify the USER MESSAGE into exactly one label:

- "claim": a factual statement or a request to verify something.
- "chat": greetings, thanks, small talk, or questions about how you work.
- "follow_up": a question that refers to the PREVIOUS fact-check result \
(e.g. "why?", "what's the source?", "explain more", "are you sure?").

Rules:
- If HAS_PREVIOUS_VERDICT is false, you may only pick "claim" or "chat".
- The user may write in English or Hindi/Hinglish. Understand both.

HAS_PREVIOUS_VERDICT: {has_prev}
USER MESSAGE: "{message}"

Respond with ONLY a JSON object:
{{"intent": "claim|chat|follow_up", "reason": "short reason"}}"""


def route(message: str, has_previous_verdict: bool) -> dict:
    msg = (message or "").strip()
    if not msg:
        return {"intent": "chat", "reason": "empty message"}

    prompt = _ROUTER_PROMPT.format(
        has_prev=str(bool(has_previous_verdict)).lower(),
        message=msg.replace('"', "'"),
    )
    result = llm.call_llm_json(
        prompt, reasoning=False,
        default={"intent": "claim", "reason": "fallback"},
    )
    intent = result.get("intent", "claim")
    if intent == "follow_up" and not has_previous_verdict:
        intent = "claim"
    if intent not in ("claim", "chat", "follow_up"):
        intent = "claim"
    return {"intent": intent, "reason": result.get("reason", "")}
