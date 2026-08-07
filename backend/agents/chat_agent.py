"""Chat Agent — casual replies + follow-up answers (reuse previous verdict)."""
from backend import llm

_CASUAL_PROMPT = """You are TruthLens, a professional AI fact-checking assistant.
Reply briefly and warmly to the user's casual message (1-3 sentences). If they
ask what you can do, explain you verify text, audio, or image claims and return
a verdict (Real / Fake / Misleading / Manipulated / Inconclusive) with evidence.
The user may write in Hindi or English; reply in clear English.

CONVERSATION SO FAR:
{history}

USER: "{message}"
TruthLens:"""

_FOLLOWUP_PROMPT = """You are TruthLens. The user is asking a follow-up about the
PREVIOUS fact-check below. Answer using ONLY that result and its evidence. Do NOT
invent new facts. If the answer isn't in the evidence, say you'd need a fresh check.

PREVIOUS VERDICT: {verdict} (confidence {confidence})
PREVIOUS SUMMARY: {summary}
EVIDENCE:
{evidence}

USER FOLLOW-UP: "{message}"
TruthLens:"""


def _fmt_history(history, limit=6):
    lines = []
    for m in (history or [])[-limit:]:
        role = "USER" if m.get("role") == "user" else "TruthLens"
        lines.append(f"{role}: {m.get('content','')}")
    return "\n".join(lines) if lines else "(no prior messages)"


def casual_reply(message: str, history: list) -> str:
    prompt = _CASUAL_PROMPT.format(
        history=_fmt_history(history), message=(message or "").replace('"', "'"))
    try:
        return llm.call_llm(prompt, reasoning=False).strip()
    except Exception:
        return ("Hi! I'm TruthLens. Share any claim as text, audio, or image "
                "and I'll verify it with evidence.")


def follow_up_reply(message: str, last_verdict: dict) -> str:
    lv = last_verdict or {}
    ev_lines = []

    for e in (lv.get("evidence") or [])[:5]:
        ev_lines.append(f"- {e.get('title','')} ({e.get('source_type','')}): "
                        f"{e.get('snippet','')}")

    prompt = _FOLLOWUP_PROMPT.format(
        verdict=lv.get("verdict", "Inconclusive"),
        confidence=round(lv.get("confidence", 0.0), 2),
        summary=lv.get("summary", ""),
        evidence="\n".join(ev_lines) if ev_lines else "(no evidence stored)",
        message=(message or "").replace('"', "'"))

    try:
        return llm.call_llm(prompt, reasoning=False).strip()
        
    except Exception:
        return (f"Based on the previous check, the verdict was "
                f"{lv.get('verdict','Inconclusive')}. Ask me to run a fresh check.")
