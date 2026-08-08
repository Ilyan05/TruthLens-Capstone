"""Tree of Thought (LangGraph) + Reflection (Option B) + Phase 6 forgery -> Manipulated."""
from typing import TypedDict, List
from backend import llm, config
from backend.services import legal_rag
from backend.tools.tools import legal_rag_tool


class VerificationState(TypedDict, total=False):
    claim: str
    search_query: str
    pre_grounder: dict
    evidence: List[dict]
    legal_evidence: List[dict]
    is_legal: bool
    forgery: dict
    branches: dict
    verdict: str
    confidence: float
    summary: str
    needs_human_review: bool
    reflection: dict


def _evidence_block(state, include_legal=True):
    lines = []
    for i, e in enumerate(state.get("evidence", [])):
        lines.append(f"[{i}] ({e.get('source_type','web')}, stance={e.get('stance','neutral')}) "
                     f"{e.get('title','')} :: {e.get('snippet','')}")
    if include_legal:
        for j, e in enumerate(state.get("legal_evidence", [])):
            lines.append(f"[L{j}] (LAW: {e.get('law','')}) {e.get('snippet','')}")
    return "\n".join(lines) if lines else "(no evidence)"


def _bl(prompt, default):
    return llm.call_llm_json(prompt, reasoning=True, default=default)


def _norm(r):
    try:
        s = float(r.get("score", 0.0))
    except (TypeError, ValueError):
        s = 0.0
    return {"score": max(0.0, min(1.0, s)), "summary": r.get("summary", ""),
            "citations": r.get("citations", []) if isinstance(r.get("citations"), list) else []}


def node_gather_legal(state):
    claim = state.get("claim", "")
    state["is_legal"] = legal_rag.is_legal_claim(claim)
    if state["is_legal"]:
        try:
            state["legal_evidence"] = legal_rag_tool.invoke(state.get("search_query") or claim)
        except Exception:
            state["legal_evidence"] = legal_rag.search_law(claim)
    else:
        state["legal_evidence"] = []
    return state


def node_supporting(state):
    p = f"""SUPPORTING branch. Consider ONLY evidence that SUPPORTS the claim.
CLAIM: "{state.get('claim','')}"
EVIDENCE:
{_evidence_block(state)}
Return ONLY JSON:
{{"score": 0.0, "summary": "what supports the claim, or 'none'", "citations": [indices]}}
score 0.0-1.0 = strength of supporting evidence."""
    r = _branch_llm(prompt, {"score": 0.0, "summary": "none", "citations": []})
    state.setdefault("branches", {})["supporting"] = _norm_branch(r)
    return state


def node_contradicting(state):
    p = f"""CONTRADICTING branch. Consider ONLY evidence that REFUTES the claim.
CLAIM: "{state.get('claim','')}"
EVIDENCE:
{_evidence_block(state)}
Return ONLY JSON: {{"score":0.0,"summary":"what contradicts it, or 'none'","citations":[indices]}}"""
    state.setdefault("branches", {})["contradicting"] = _norm(_bl(p, {"score": 0.0, "summary": "none", "citations": []}))
    return state


def node_context(state):
    note = ("This is a LEGAL/constitutional claim. Use the LAW sections (BNS 2023 primary; IPC 1860 only "
            "for older cases). Labels like 'anti-national' are opinions, not defined offences."
            if state.get("is_legal")
            else "Check timeline, location, and whether old content is reused out of context.")
    p = f"""CONTEXT branch. {note}
CLAIM: "{state.get('claim','')}"
EVIDENCE:
{_evidence_block(state)}
Return ONLY JSON: {{"score":0.0,"summary":"context/legal assessment","issue":"none|timeline|location|legal|opinion"}}"""
    r = _bl(p, {"score": 0.5, "summary": "", "issue": "none"})
    b = _norm(r); b["issue"] = r.get("issue", "none")
    state.setdefault("branches", {})["context"] = b
    return state


def node_source(state):
    p = f"""SOURCE CREDIBILITY branch. Judge how trustworthy the sources are by reasoning.
CLAIM: "{state.get('claim','')}"
EVIDENCE:
{_evidence_block(state, include_legal=False)}
Return ONLY JSON: {{"score":0.0,"summary":"overall source reliability"}}"""
    state.setdefault("branches", {})["source_credibility"] = _norm(_bl(p, {"score": 0.5, "summary": ""}))
    return state


def node_aggregate(state):
    b = state.get("branches", {})
    sup = b.get("supporting", {}).get("score", 0.0)
    con = b.get("contradicting", {}).get("score", 0.0)
    ctx = b.get("context", {}).get("score", 0.5)
    src = b.get("source_credibility", {}).get("score", 0.5)
    pg = state.get("pre_grounder", {})
    pg_conf = pg.get("initial_confidence", 0.0)
    pg_true = pg.get("initial_assessment") == "likely_true"
    w = config.TOT_WEIGHTS
    esig = (sup - con + 1) / 2
    psig = pg_conf if pg_true else (1 - pg_conf)
    combined = w["evidence"] * esig + w["source"] * src + w["context"] * ctx + w["pregrounder"] * psig
    total = len(state.get("evidence", []))
    reliable = sum(1 for e in state.get("evidence", []) if e.get("source_type") in ("factcheck", "news", "official", "encyclopedia"))
    issue = b.get("context", {}).get("issue", "none")
    risk_high = pg.get("risk_level") == "high"
    review = risk_high

    forgery = state.get("forgery") or {}
    forged = forgery.get("label") == "likely_edited"
    fconf = forgery.get("confidence", 0.0)

    if forged and fconf >= 0.6:
        verdict = "Manipulated"; confidence = round(max(0.6, fconf), 2); review = True
    elif total < config.MIN_SOURCES or reliable == 0:
        verdict, confidence = "Inconclusive", round(min(combined, 0.55), 2); review = True
    elif issue == "opinion" or (state.get("is_legal") and issue == "legal"):
        verdict, confidence = "Misleading", round(max(0.6, combined), 2); review = True
    elif con > sup and con >= 0.5:
        verdict = "Fake"; confidence = round(min(0.55 + con * 0.4, 0.95), 2)
    elif sup > con and sup >= 0.5:
        verdict = "Real"; confidence = round(min(0.55 + sup * 0.4, 0.95), 2)
    elif issue in ("timeline", "location"):
        verdict, confidence = "Misleading", round(max(0.6, combined), 2)
    else:
        verdict, confidence = "Inconclusive", round(combined, 2)
    if confidence < config.MIN_CONFIDENCE and verdict in ("Real", "Fake"):
        verdict = "Inconclusive"; review = True

    bits = []
    if verdict == "Manipulated":
        bits.append("Image shows signs of editing/manipulation.")
        bits += forgery.get("reasons", [])[:2]
    elif con > sup:
        bits.append(b.get("contradicting", {}).get("summary", ""))
    elif sup > con:
        bits.append(b.get("supporting", {}).get("summary", ""))
    bits.append(b.get("context", {}).get("summary", ""))
    summary = f"Verdict: {verdict}. " + " ".join(x for x in bits if x and x != "none")
    if state.get("is_legal"):
        summary += " " + config.LEGAL_DISCLAIMER
    state.update({"verdict": verdict, "confidence": confidence, "summary": summary.strip(),
                  "needs_human_review": review})
    return state


def node_reflection(state):
    if not config.REFLECTION_ENABLED:
        state["reflection"] = {"skipped": True}
        return state
    p = f"""You are the REFLECTION / EVALUATOR (LLM-as-judge). Review the DRAFT verdict vs evidence.
Check groundedness (supported by evidence? no hallucination), consistency, confidence.
CLAIM: "{state.get('claim','')}"
DRAFT VERDICT: {state.get('verdict')} (confidence {state.get('confidence')})
BRANCH SCORES: {state.get('branches')}
IMAGE FORGERY: {state.get('forgery')}
EVIDENCE:
{_evidence_block(state)}
Return ONLY JSON:
{{"approved":true,"adjusted_verdict":"keep-or-new label","adjusted_confidence":0.0,"hallucination":false,"note":"one short sentence"}}
If NOT well grounded, set approved=false and adjust (often to "Inconclusive")."""
    d = {"approved": True, "adjusted_verdict": state.get("verdict"),
         "adjusted_confidence": state.get("confidence"), "hallucination": False,
         "note": "auto-approved (fallback)"}
    r = llm.call_llm_json(p, reasoning=True, default=d)
    approved = bool(r.get("approved", True))
    new_v = r.get("adjusted_verdict") or state.get("verdict")
    try:
        new_c = float(r.get("adjusted_confidence", state.get("confidence", 0.0)))
    except (TypeError, ValueError):
        new_c = state.get("confidence", 0.0)
    hallu = bool(r.get("hallucination", False))
    if new_v in config.VERDICT_LABELS:
        if not approved or hallu:
            state["needs_human_review"] = True
        if new_v != state.get("verdict") or abs(new_c - state.get("confidence", 0)) > 0.001:
            state["verdict"] = new_v
            state["confidence"] = round(max(0.0, min(1.0, new_c)), 2)
            state["summary"] += f"  [Reviewed: {r.get('note','')}]"
    state["reflection"] = {"approved": approved, "hallucination": hallu, "note": r.get("note", ""),
                           "verdict": state["verdict"], "confidence": state["confidence"]}
    return state


def build_graph():
    from langgraph.graph import StateGraph, START, END
    g = StateGraph(VerificationState)
    for n, fn in [("gather_legal", node_gather_legal), ("supporting", node_supporting),
                  ("contradicting", node_contradicting), ("context", node_context),
                  ("source_credibility", node_source), ("aggregate", node_aggregate),
                  ("reflection", node_reflection)]:
        g.add_node(n, fn)
    g.add_edge(START, "gather_legal")
    g.add_edge("gather_legal", "supporting")
    g.add_edge("supporting", "contradicting")
    g.add_edge("contradicting", "context")
    g.add_edge("context", "source_credibility")
    g.add_edge("source_credibility", "aggregate")
    g.add_edge("aggregate", "reflection")
    g.add_edge("reflection", END)
    return g.compile()


_compiled = None


def get_compiled():
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


def tot_steps(claim, search_query, evidence, pre_grounder, forgery=None):
    state = {"claim": claim, "search_query": search_query, "evidence": evidence,
             "pre_grounder": pre_grounder, "branches": {}, "forgery": forgery}
    state = node_gather_legal(state)
    yield ("legal", {"is_legal": state.get("is_legal"), "count": len(state.get("legal_evidence", []))})
    for name, fn in (("supporting", node_supporting), ("contradicting", node_contradicting),
                     ("context", node_context), ("source_credibility", node_source)):
        state = fn(state)
        yield (name, state["branches"][name])
    state = node_aggregate(state)
    yield ("draft", {"verdict": state["verdict"], "confidence": state["confidence"]})
    state = node_reflection(state)
    yield ("reflection", state.get("reflection", {}))
    yield ("verdict", {"verdict": state["verdict"], "confidence": state["confidence"],
                       "summary": state["summary"], "needs_human_review": state["needs_human_review"],
                       "branches": state["branches"], "is_legal": state.get("is_legal", False),
                       "legal_evidence": state.get("legal_evidence", []),
                       "forgery": state.get("forgery"), "reflection": state.get("reflection", {})})
