from backend import llm

_P = """
Analyze evidence for a fact-check.
For EACH item, decide stance toward the CLAIM:
"supporting" | "contradicting" | "neutral"

CLAIM: "{claim}"

EVIDENCE ITEMS:
{items}

Return ONLY a JSON array in order:

[
    {{
        "index": 0,
        "stance": "supporting|contradicting|neutral",
        "relevance": 0.0,
        "note": "short"
    }}
]
"""


def _fmt(ev):
    return "\n".join(
        f"[{i}] ({e.get('source_type', 'web')}) "
        f"{e.get('title', '')} :: "
        f"{e.get('snippet', '')}"
        for i, e in enumerate(ev)
    )


def build_context(claim_text, evidence):
    if not evidence:
        return {
            "evidence": [],
            "supporting_count": 0,
            "contradicting_count": 0,
            "neutral_count": 0,
            "reliable_sources": 0
        }

    p = _P.format(
        claim=(claim_text or "").replace('"', "'"),
        items=_fmt(evidence)
    )

    tags = llm.call_llm_json(
        p,
        reasoning=False,
        default=[]
    )

    bi = {}

    if isinstance(tags, list):
        for t in tags:
            if isinstance(t, dict) and "index" in t:
                bi[t["index"]] = t

    sup = 0
    con = 0
    neu = 0
    rel = 0
    out = []

    for i, e in enumerate(evidence):
        t = bi.get(i, {})

        st = t.get("stance", "neutral")
        if st not in ("supporting", "contradicting", "neutral"):
            st = "neutral"

        try:
            rv = float(t.get("relevance", 0.5))
        except (TypeError, ValueError):
            rv = 0.5

        it = dict(e)
        it["stance"] = st
        it["relevance"] = max(0.0, min(1.0, rv))
        it["note"] = t.get("note", "")

        out.append(it)

        if st == "supporting":
            sup += 1
        elif st == "contradicting":
            con += 1
        else:
            neu += 1

        if e.get("source_type") in (
            "factcheck",
            "news",
            "official",
            "encyclopedia"
        ):
            rel += 1

    out.sort(
        key=lambda x: x.get("relevance", 0),
        reverse=True
    )

    return {
        "evidence": out,
        "supporting_count": sup,
        "contradicting_count": con,
        "neutral_count": neu,
        "reliable_sources": rel
    }