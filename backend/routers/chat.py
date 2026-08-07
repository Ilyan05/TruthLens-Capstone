import json
import asyncio
from fastapi import APIRouter, Form, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Optional

from backend import config, memory
from backend.agents import router_agent, claim_agent, pregrounder, chat_agent
from backend.services import websearch, context_builder

router = APIRouter(prefix="/api/v1", tags=["chat"])


def sse(event: str, data: dict) -> str:
    return f"data: {json.dumps({'event': event, **data})}\n\n"


async def _type_out(text: str, chunk_words: int = 2, delay: float = 0.03):
    words = (text or "").split(" ")
    yield sse("answer_start", {})
    buf = []
    for w in words:
        buf.append(w)
        if len(buf) >= chunk_words:
            yield sse("answer_chunk", {"text": " ".join(buf) + " "})
            buf = []
            await asyncio.sleep(delay)
    if buf:
        yield sse("answer_chunk", {"text": " ".join(buf) + " "})


_ASSESS_TO_VERDICT = {
    "likely_true": "Real",
    "likely_false": "Fake",
    "unclear": "Inconclusive",
}


def _evidence_verdict(pg: dict, ctx: dict) -> tuple:
    """
    Phase 3 preliminary evidence-based decision (real Tree-of-Thought = Phase 4).
    Uses stance counts + reliable-source count + guardrails.
    Returns (verdict_label, confidence, summary_core, needs_review).
    """
    sup = ctx["supporting_count"]
    con = ctx["contradicting_count"]
    reliable = ctx["reliable_sources"]
    total = len(ctx["evidence"])
    risk_high = pg.get("risk_level") == "high"

    # Guardrail: not enough evidence -> Inconclusive
    if total < config.MIN_SOURCES or reliable == 0:
        return ("Inconclusive", 0.4,
                "There isn't enough reliable evidence yet to reach a confident "
                "verdict.", True if risk_high else False)

    # Decide by stance majority
    if con > sup:
        label = "Fake"
        conf = min(0.6 + 0.1 * (con - sup), 0.9)
    elif sup > con:
        label = "Real"
        conf = min(0.6 + 0.1 * (sup - con), 0.9)
    else:
        label = "Inconclusive"
        conf = 0.5

    # Guardrail: below MIN_CONFIDENCE -> Inconclusive
    if conf < config.MIN_CONFIDENCE:
        label = "Inconclusive"

    core = (f"Based on {total} sources ({sup} supporting, {con} contradicting, "
            f"{reliable} from reliable outlets), the current assessment is "
            f"{label}.")
    review = risk_high or label == "Inconclusive"
    return (label, round(conf, 2), core, review)


async def pipeline(session_id, message, input_type, has_file, filename):
    # 0) no key -> friendly guidance
    if not config.llm_ready():
        yield sse("step", {"stage": "config", "text": "Checking configuration..."})
        await asyncio.sleep(0.3)
        msg = ("TruthLens is set up correctly, but no Gemini API key was found. "
               "Add your free key to the .env file (GEMINI_API_KEY=...) and "
               "restart. Get one at https://aistudio.google.com/apikey")
        async for c in _type_out(msg):
            yield c
        yield sse("done", {})
        return

    memory.add_message(session_id, "user", message or f"({input_type} file)")

    # audio/image note (Phase 5)
    if has_file and input_type in ("audio", "image"):
        yield sse("step", {"stage": "upload",
                           "text": f"Received {input_type} file: {filename}"})
        await asyncio.sleep(0.3)
        note = (f"Thanks! {input_type.capitalize()} understanding "
                f"(transcription / OCR / vision / forgery) is being wired in "
                f"Phase 5. For now, please type a claim and I'll verify it.")
        async for c in _type_out(note):
            yield c
        yield sse("done", {})
        return

    # 1) INTENT ROUTER
    yield sse("step", {"stage": "router", "text": "Understanding your message..."})
    has_prev = memory.has_verdict(session_id)
    intent_res = await asyncio.to_thread(router_agent.route, message, has_prev)
    intent = intent_res["intent"]

    # 2a) CASUAL CHAT
    if intent == "chat":
        yield sse("step", {"stage": "chat", "text": "Composing a reply..."})
        history = memory.get_history(session_id)
        reply = await asyncio.to_thread(chat_agent.casual_reply, message, history)
        async for c in _type_out(reply):
            yield c
        memory.add_message(session_id, "assistant", reply)
        yield sse("done", {})
        return

    # 2b) FOLLOW-UP
    if intent == "follow_up":
        yield sse("step", {"stage": "follow_up",
                           "text": "Looking back at the previous result..."})
        last = memory.get_last_verdict(session_id)
        reply = await asyncio.to_thread(chat_agent.follow_up_reply, message, last)
        async for c in _type_out(reply):
            yield c
        memory.add_message(session_id, "assistant", reply)
        yield sse("done", {})
        return

    # 2c) CLAIM -> verification pipeline
    yield sse("step", {"stage": "claim", "text": "Extracting the core claim..."})
    claim = await asyncio.to_thread(claim_agent.extract_claim, message)
    yield sse("step", {"stage": "claim_done",
                       "text": f"Claim: \"{claim.get('claim_text','')}\""})

    if claim.get("claim_type") in ("opinion", "satire"):
        note = (f"This looks like {claim.get('claim_type')} rather than a factual "
                f"claim, so it can't be fact-checked as true/false. Share a "
                f"factual statement and I'll verify it.")
        async for c in _type_out(note):
            yield c
        verdict = {"verdict": "Inconclusive", "confidence": 0.0,
                   "summary": note, "evidence": []}
        memory.set_last_verdict(session_id, verdict)
        memory.add_message(session_id, "assistant", note)
        yield sse("verdict", verdict)
        yield sse("done", {})
        return

    # Pre-Grounder
    yield sse("step", {"stage": "pregrounder",
                       "text": "Running an initial assessment..."})
    pg = await asyncio.to_thread(pregrounder.pre_ground, claim.get("claim_text", ""))
    conf0 = pg.get("initial_confidence", 0.0)
    risk = pg.get("risk_level", "high")
    yield sse("step", {"stage": "assess",
                       "text": (f"Initial: {pg.get('initial_assessment')} · "
                                f"confidence {round(conf0*100)}% · risk {risk}")})

    # ---- FAST PATH ----
    if pg.get("fast_path"):
        yield sse("step", {"stage": "fastpath",
                           "text": "High confidence & low risk - fast path."})
        label = _ASSESS_TO_VERDICT.get(pg.get("initial_assessment"), "Inconclusive")
        summary = (f"Verdict: {label}. {pg.get('reason','')} "
                   f"(Fast-path: well-established fact; full evidence cross-check "
                   f"skipped by design for high-confidence low-risk claims.)")
        verdict = {"verdict": label, "confidence": round(conf0, 2),
                   "summary": summary, "evidence": [],
                   "reasoning": {"claim": claim, "pre_grounder": pg},
                   "needs_human_review": False}
        async for c in _type_out(summary):
            yield c
        memory.set_last_verdict(session_id, verdict)
        memory.add_message(session_id, "assistant", summary)
        yield sse("verdict", verdict)
        yield sse("done", {})
        return

    # ---- CROSS-CHECK: Web Search ----
    yield sse("step", {"stage": "search",
                       "text": "Searching trusted sources (fact-check, news, Wikipedia)..."})
    raw_evidence = await asyncio.to_thread(
        websearch.search_evidence, claim.get("search_query", ""),
        claim.get("claim_text", ""))
    yield sse("step", {"stage": "search_done",
                       "text": f"Found {len(raw_evidence)} sources."})

    # ---- Context-NL Builder (stance tagging) ----
    yield sse("step", {"stage": "context",
                       "text": "Analyzing evidence stance (supporting / contradicting)..."})
    ctx = await asyncio.to_thread(
        context_builder.build_context, claim.get("claim_text", ""), raw_evidence)
    yield sse("step", {"stage": "context_done",
                       "text": (f"Evidence: {ctx['supporting_count']} supporting · "
                                f"{ctx['contradicting_count']} contradicting · "
                                f"{ctx['neutral_count']} neutral")})

    # ---- Preliminary evidence-based verdict (full ToT engine = Phase 4) ----
    label, conf, core, review = _evidence_verdict(pg, ctx)
    summary = (f"{core} A full Tree-of-Thought verification (Phase 4) will "
               f"finalize this with deeper multi-branch reasoning.")

    # top evidence for the card (max 5)
    ev_for_card = [{
        "title": e.get("title", ""),
        "url": e.get("url", ""),
        "source_type": e.get("source_type", "web"),
        "snippet": e.get("snippet", ""),
        "stance": e.get("stance", "neutral"),
    } for e in ctx["evidence"][:5]]

    verdict = {
        "verdict": label,
        "confidence": conf,
        "summary": summary,
        "evidence": ev_for_card,
        "reasoning": {"claim": claim, "pre_grounder": pg,
                      "stance_counts": {
                          "supporting": ctx["supporting_count"],
                          "contradicting": ctx["contradicting_count"],
                          "neutral": ctx["neutral_count"]}},
        "needs_human_review": review,
    }

    async for c in _type_out(summary):
        yield c
    memory.set_last_verdict(session_id, verdict)
    memory.add_message(session_id, "assistant", summary)
    yield sse("verdict", verdict)
    yield sse("done", {})


@router.post("/chat")
async def chat(
    session_id: str = Form(...),
    message: str = Form(""),
    input_type: str = Form("text"),
    file: Optional[UploadFile] = File(None),
):
    has_file = file is not None
    filename = file.filename if has_file else ""
    return StreamingResponse(
        pipeline(session_id, message, input_type, has_file, filename),
        media_type="text/event-stream",
    )


@router.post("/reset")
async def reset(session_id: str = Form(...)):
    memory.reset(session_id)
    return {"status": "ok"}
