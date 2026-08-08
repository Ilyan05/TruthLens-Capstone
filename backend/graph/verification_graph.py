"""
🌳 TREE OF THOUGHT — Verification Graph (PHASE 4, the star of TruthLens)

Built with LangGraph StateGraph. The 4 Tree-of-Thought branches are graph NODES
that each reason about the claim from one perspective, then an aggregator node
combines their scores into a final verdict.

           ┌──────────────┐
   START → │ gather_tools │  (web_search_tool + legal_rag_tool if legal claim)
           └──────┬───────┘
                  ▼
        ┌─────────────────────────────────────────┐
        │  supporting → contradicting → context → │   (4 ToT branch nodes)
        │  source_credibility                     │
        └──────────────────┬──────────────────────┘
                           ▼
                    ┌──────────────┐
                    │  aggregate   │ → verdict → END
                    └──────────────┘

Design notes:
  - TOOLS ARE HYBRID: the graph orchestrates them in `gather_tools`, and they are
    also BOUND to the LLM (see build_tool_binding) to demonstrate agentic tool use.
  - Branches run sequentially (free-tier friendly) but each is an independent
    reasoning path — that is the essence of Tree of Thought.
  - Everything degrades gracefully; a failed branch just yields a neutral score.

The graph is wrapped by `run_tree_of_thought(...)` which also acts as a generator
of progress events so the router can stream branch scores live to the UI.
"""
from typing import TypedDict, List
from backend import llm, config
from backend.services import legal_rag
from backend.tools.tools import web_search_tool, legal_rag_tool


# ---------------- shared state ----------------
class VerificationState(TypedDict, total=False):
    claim: str
    search_query: str
    pre_grounder: dict
    evidence: List[dict]          # stance-tagged evidence (from context builder)
    legal_evidence: List[dict]    # law sections (if legal claim)
    is_legal: bool
    branches: dict                # each branch: {score, summary, citations}
    verdict: str
    confidence: float
    summary: str
    needs_human_review: bool


# ---------------- helpers ----------------
def _evidence_block(state, include_legal=True):
    lines = []
    for i, e in enumerate(state.get("evidence", [])):
        lines.append(f"[{i}] ({e.get('source_type','web')}, stance={e.get('stance','neutral')}) "
                     f"{e.get('title','')} :: {e.get('snippet','')}")
    if include_legal:
        for j, e in enumerate(state.get("legal_evidence", [])):
            lines.append(f"[L{j}] (LAW: {e.get('law','')}) {e.get('snippet','')}")
    return "\n".join(lines) if lines else "(no evidence)"


def _branch_llm(prompt, default):
    return llm.call_llm_json(prompt, reasoning=True, default=default)


# ---------------- NODE 0: gather tools (orchestrated) ----------------
def node_gather_legal(state: VerificationState) -> VerificationState:
    """If the claim is legal, call the legal RAG tool to fetch BNS/Constitution."""
    claim = state.get("claim", "")
    is_legal = legal_rag.is_legal_claim(claim)
    state["is_legal"] = is_legal
    if is_legal:
        # tool call (orchestrated). The same tool is also LLM-bindable.
        try:
            state["legal_evidence"] = legal_rag_tool.invoke(state.get("search_query") or claim)
        except Exception:
            state["legal_evidence"] = legal_rag.search_law(claim)
    else:
        state["legal_evidence"] = []
    return state


# ---------------- NODE 1: Supporting branch ----------------
def node_supporting(state: VerificationState) -> VerificationState:
    prompt = f"""You are the SUPPORTING branch of a Tree-of-Thought fact-checker.
Consider ONLY evidence that SUPPORTS the claim.
CLAIM: "{state.get('claim','')}"
EVIDENCE:
{_evidence_block(state)}
Return ONLY JSON:
{{"score": 0.0, "summary": "what supports the claim, or 'none'", "citations": [indices]}}
score 0.0-1.0 = strength of supporting evidence."""
    
    r = _branch_llm(prompt, {"score": 0.0, "summary": "none", "citations": []})
    state.setdefault("branches", {})["supporting"] = _norm_branch(r)
    return state


# ---------------- NODE 2: Contradicting branch ----------------
def node_contradicting(state: VerificationState) -> VerificationState:
    prompt = f"""You are the CONTRADICTING branch of a Tree-of-Thought fact-checker.
Consider ONLY evidence that REFUTES/CONTRADICTS the claim.
CLAIM: "{state.get('claim','')}"
EVIDENCE:
{_evidence_block(state)}
Return ONLY JSON:
{{"score": 0.0, "summary": "what contradicts the claim, or 'none'", "citations": [indices]}}
score 0.0-1.0 = strength of contradicting evidence."""
    r = _branch_llm(prompt, {"score": 0.0, "summary": "none", "citations": []})
    state.setdefault("branches", {})["contradicting"] = _norm_branch(r)
    return state


# ---------------- NODE 3: Context branch (uses legal context) ----------------
def node_context(state: VerificationState) -> VerificationState:
    legal_note = ("This is a LEGAL/constitutional claim. Use the LAW sections above. "
                  "Remember: labels like 'anti-national' are opinions, not defined "
                  "legal offences; sedition-type provisions are under BNS 2023."
                  if state.get("is_legal") else
                  "Check timeline, location, and whether old content is reused out of context.")
    prompt = f"""You are the CONTEXT branch of a Tree-of-Thought fact-checker.
{legal_note}
CLAIM: "{state.get('claim','')}"
EVIDENCE:
{_evidence_block(state)}
Return ONLY JSON:
{{"score": 0.0, "summary": "context/timeline/legal assessment", "issue": "none|timeline|location|legal|opinion"}}
score 0.0-1.0 = how well the claim holds up in proper context (higher = consistent)."""
    r = _branch_llm(prompt, {"score": 0.5, "summary": "", "issue": "none"})
    b = _norm_branch(r)
    b["issue"] = r.get("issue", "none")
    state.setdefault("branches", {})["context"] = b
    return state


# ---------------- NODE 4: Source credibility branch ----------------
def node_source(state: VerificationState) -> VerificationState:
    prompt = f"""You are the SOURCE CREDIBILITY branch of a Tree-of-Thought fact-checker.
Judge how trustworthy the sources are, using reasoning (NOT a fixed rule). Consider
fact-check sites, established news, official/govt, encyclopedias vs unknown blogs.
CLAIM: "{state.get('claim','')}"
EVIDENCE:
{_evidence_block(state, include_legal=False)}
Return ONLY JSON:
{{"score": 0.0, "summary": "overall source reliability"}}
score 0.0-1.0 = overall reliability of the sources."""
    r = _branch_llm(prompt, {"score": 0.5, "summary": ""})
    state.setdefault("branches", {})["source_credibility"] = _norm_branch(r)
    return state


# ---------------- NODE 5: Aggregate -> verdict ----------------
def node_aggregate(state: VerificationState) -> VerificationState:
    b = state.get("branches", {})
    sup = b.get("supporting", {}).get("score", 0.0)
    con = b.get("contradicting", {}).get("score", 0.0)
    ctx = b.get("context", {}).get("score", 0.5)
    src = b.get("source_credibility", {}).get("score", 0.5)
    pg = state.get("pre_grounder", {})
    pg_conf = pg.get("initial_confidence", 0.0)
    pg_true = pg.get("initial_assessment") == "likely_true"

    w = config.TOT_WEIGHTS
    # evidence signal: +sup, -con  => net in [-1, 1] -> map to [0,1]
    evidence_signal = (sup - con + 1) / 2
    pg_signal = pg_conf if pg_true else (1 - pg_conf)
    combined = (w["evidence"] * evidence_signal +
                w["source"] * src +
                w["context"] * ctx +
                w["pregrounder"] * pg_signal)

    total_sources = len(state.get("evidence", []))
    reliable = sum(1 for e in state.get("evidence", [])
                   if e.get("source_type") in ("factcheck", "news", "official", "encyclopedia"))
    issue = b.get("context", {}).get("issue", "none")
    risk_high = pg.get("risk_level") == "high"

    # ----- decision + guardrails -----
    review = risk_high
    if total_sources < config.MIN_SOURCES or reliable == 0:
        verdict, confidence = "Inconclusive", round(min(combined, 0.55), 2)
        review = True
    elif issue == "opinion" or (state.get("is_legal") and issue == "legal"):
        # opinion/legal label -> Misleading, not a hard true/false
        verdict, confidence = "Misleading", round(max(0.6, combined), 2)
        review = True
    elif con > sup and con >= 0.5:
        verdict = "Fake"
        confidence = round(min(0.55 + con * 0.4, 0.95), 2)
    elif sup > con and sup >= 0.5:
        verdict = "Real"
        confidence = round(min(0.55 + sup * 0.4, 0.95), 2)
    elif issue in ("timeline", "location"):
        verdict, confidence = "Misleading", round(max(0.6, combined), 2)
    else:
        verdict, confidence = "Inconclusive", round(combined, 2)

    # confidence guardrail
    if confidence < config.MIN_CONFIDENCE and verdict in ("Real", "Fake"):
        verdict = "Inconclusive"
        review = True

    # ----- natural-language summary -----
    reason_bits = []
    if con > sup:
        reason_bits.append(b.get("contradicting", {}).get("summary", ""))
    elif sup > con:
        reason_bits.append(b.get("supporting", {}).get("summary", ""))
    reason_bits.append(b.get("context", {}).get("summary", ""))
    summary = f"Verdict: {verdict}. " + " ".join(x for x in reason_bits if x and x != "none")
    if state.get("is_legal"):
        summary += " " + config.LEGAL_DISCLAIMER

    state["verdict"] = verdict
    state["confidence"] = confidence
    state["summary"] = summary.strip()
    state["needs_human_review"] = review
    return state


def _norm_branch(r):
    try:
        s = float(r.get("score", 0.0))
    except (TypeError, ValueError):
        s = 0.0
    return {"score": max(0.0, min(1.0, s)),
            "summary": r.get("summary", ""),
            "citations": r.get("citations", []) if isinstance(r.get("citations"), list) else []}


# ---------------- build the compiled graph ----------------
def build_graph():
    from langgraph.graph import StateGraph, START, END
    g = StateGraph(VerificationState)
    g.add_node("gather_legal", node_gather_legal)
    g.add_node("supporting", node_supporting)
    g.add_node("contradicting", node_contradicting)
    g.add_node("context", node_context)
    g.add_node("source_credibility", node_source)
    g.add_node("aggregate", node_aggregate)

    g.add_edge(START, "gather_legal")
    g.add_edge("gather_legal", "supporting")
    g.add_edge("supporting", "contradicting")
    g.add_edge("contradicting", "context")
    g.add_edge("context", "source_credibility")
    g.add_edge("source_credibility", "aggregate")
    g.add_edge("aggregate", END)
    return g.compile()


_compiled = None


def get_compiled():
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


def run_tree_of_thought(claim, search_query, evidence, pre_grounder):
    """
    Convenience wrapper: run the full ToT graph once and return the final state.
    (chat.py uses the step-by-step version below for live streaming.)
    """
    state: VerificationState = {
        "claim": claim, "search_query": search_query,
        "evidence": evidence, "pre_grounder": pre_grounder, "branches": {},
    }
    return get_compiled().invoke(state)


# ---------------- step-by-step runner (for live UI streaming) ----------------
def tot_steps(claim, search_query, evidence, pre_grounder):
    """
    Generator that runs each node and yields (branch_name, branch_result) so the
    caller can stream live branch scores to the UI. Ends by yielding the verdict.
    """
    state: VerificationState = {
        "claim": claim, "search_query": search_query,
        "evidence": evidence, "pre_grounder": pre_grounder, "branches": {},
    }
    state = node_gather_legal(state)
    yield ("legal", {"is_legal": state.get("is_legal"),
                     "count": len(state.get("legal_evidence", []))})

    for name, fn in (("supporting", node_supporting),
                     ("contradicting", node_contradicting),
                     ("context", node_context),
                     ("source_credibility", node_source)):
        state = fn(state)
        yield (name, state["branches"][name])

    state = node_aggregate(state)
    yield ("verdict", {
        "verdict": state["verdict"], "confidence": state["confidence"],
        "summary": state["summary"], "needs_human_review": state["needs_human_review"],
        "branches": state["branches"], "is_legal": state.get("is_legal", False),
        "legal_evidence": state.get("legal_evidence", []),
    })
