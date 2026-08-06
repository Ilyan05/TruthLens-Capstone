"""
Context-NL Builder  (PHASE 3)

Takes raw evidence (from websearch) + the claim, and produces a clean,
stance-tagged context that the Verification Agent (Phase 4) can reason over.

For each evidence item it assigns a stance:
    supporting    -> backs the claim
    contradicting -> refutes the claim
    neutral       -> related but doesn't clearly support/refute

To save free-tier quota, ALL items are stance-tagged in a SINGLE LLM call
(batch), not one call per item.
"""
from backend import llm


_STANCE_PROMPT = """You are analyzing evidence for a fact-check.
For EACH evidence item below, decide its stance toward the CLAIM:
  - "supporting": the evidence supports/confirms the claim
  - "contradicting": the evidence refutes/denies the claim
  - "neutral": related but does not clearly support or contradict

CLAIM: "{claim}"

EVIDENCE ITEMS:
{items}

Return ONLY a JSON array, one object per item IN THE SAME ORDER:
[{{"index": 0, "stance": "supporting|contradicting|neutral",
   "relevance": 0.0, "note": "very short reason"}}]
relevance is 0.0-1.0 (how relevant this item is to the claim)."""


def _fmt_items(evidence: list) -> str:
    lines = []
    for i, e in enumerate(evidence):
        lines.append(f"[{i}] ({e.get('source_type','web')}) "
                     f"{e.get('title','')} :: {e.get('snippet','')}")
    return "\n".join(lines)


def build_context(claim_text: str, evidence: list) -> dict:
    """
    Return:
      {
        "evidence": [ ...same items + stance/relevance/note... ],
        "supporting_count": int,
        "contradicting_count": int,
        "neutral_count": int,
        "reliable_sources": int   # factcheck/news/official/encyclopedia
      }
    """
    if not evidence:
        return {"evidence": [], "supporting_count": 0,
                "contradicting_count": 0, "neutral_count": 0,
                "reliable_sources": 0}

    prompt = _STANCE_PROMPT.format(
        claim=(claim_text or "").replace('"', "'"),
        items=_fmt_items(evidence),
    )
    tags = llm.call_llm_json(prompt, reasoning=False, default=[])

    # map index -> tag
    by_index = {}
    if isinstance(tags, list):
        for t in tags:
            if isinstance(t, dict) and "index" in t:
                by_index[t["index"]] = t

    sup = con = neu = reliable = 0
    out_ev = []
    for i, e in enumerate(evidence):
        t = by_index.get(i, {})
        stance = t.get("stance", "neutral")
        if stance not in ("supporting", "contradicting", "neutral"):
            stance = "neutral"
        try:
            rel = float(t.get("relevance", 0.5))
        except (TypeError, ValueError):
            rel = 0.5

        item = dict(e)
        item["stance"] = stance
        item["relevance"] = max(0.0, min(1.0, rel))
        item["note"] = t.get("note", "")
        out_ev.append(item)

        if stance == "supporting":
            sup += 1
        elif stance == "contradicting":
            con += 1
        else:
            neu += 1
        if e.get("source_type") in ("factcheck", "news", "official", "encyclopedia"):
            reliable += 1

    # sort: most relevant first (nice for display + downstream)
    out_ev.sort(key=lambda x: x.get("relevance", 0), reverse=True)

    return {
        "evidence": out_ev,
        "supporting_count": sup,
        "contradicting_count": con,
        "neutral_count": neu,
        "reliable_sources": reliable,
    }
