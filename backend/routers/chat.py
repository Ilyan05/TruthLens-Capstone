"""TruthLens - Chat Router | Phase 7 (+ chat history) + forgery + Reflection."""
import json, asyncio, time
from fastapi import APIRouter, Form, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Optional
from backend import config, memory, db
from backend.agents import router_agent, claim_agent, pregrounder, chat_agent
from backend.services import websearch, context_builder, audio_service, image_service
from backend.graph import verification_graph

router = APIRouter(prefix="/api/v1", tags=["chat"])


def sse(event, data):
    return f"data: {json.dumps({'event': event, **data})}\n\n"


async def _type_out(text, cw=2, delay=0.03):
    words = (text or "").split(" ")
    yield sse("answer_start", {})
    buf = []
    for w in words:
        buf.append(w)
        if len(buf) >= cw:
            yield sse("answer_chunk", {"text": " ".join(buf) + " "}); buf = []
            await asyncio.sleep(delay)
    if buf:
        yield sse("answer_chunk", {"text": " ".join(buf) + " "})


_ASSESS = {"likely_true": "Real", "likely_false": "Fake", "unclear": "Inconclusive"}
_BRANCH = {"supporting": "Supporting", "contradicting": "Contradicting",
           "context": "Context", "source_credibility": "Source Credibility"}


async def _run_claim(session_id, message, forgery=None, input_type="text"):
    _t0 = time.time()
    yield sse("step", {"stage": "claim", "text": "Extracting the core claim..."})
    claim = await asyncio.to_thread(claim_agent.extract_claim, message)
    yield sse("step", {"stage": "claim_done", "text": f"Claim: \"{claim.get('claim_text','')}\""})
    if claim.get("claim_type") in ("opinion", "satire"):
        note = f"This looks like {claim.get('claim_type')} rather than a factual claim."
        async for c in _type_out(note): yield c
        v = {"verdict": "Inconclusive", "confidence": 0.0, "summary": note, "evidence": []}
        memory.set_last_verdict(session_id, v, claim_text=claim.get("claim_text", ""), input_type=input_type)
        memory.add_message(session_id, "assistant", note)
        yield sse("verdict", v); yield sse("done", {}); return

    yield sse("step", {"stage": "pregrounder", "text": "Running an initial assessment..."})
    pg = await asyncio.to_thread(pregrounder.pre_ground, claim.get("claim_text", ""))
    conf0 = pg.get("initial_confidence", 0.0); risk = pg.get("risk_level", "high")
    yield sse("step", {"stage": "assess",
                       "text": f"Initial: {pg.get('initial_assessment')} · confidence {round(conf0*100)}% · risk {risk}"})

    if pg.get("fast_path") and not forgery:
        yield sse("step", {"stage": "fastpath", "text": "High confidence & low risk - fast path."})
        label = _ASSESS.get(pg.get("initial_assessment"), "Inconclusive")
        summary = f"Verdict: {label}. {pg.get('reason','')} (Fast-path.)"
        v = {"verdict": label, "confidence": round(conf0, 2), "summary": summary, "evidence": [], "needs_human_review": False}
        async for c in _type_out(summary): yield c
        memory.set_last_verdict(session_id, v, claim_text=claim.get("claim_text", ""), input_type=input_type)
        memory.add_message(session_id, "assistant", summary)
        yield sse("verdict", v); yield sse("done", {}); return

    yield sse("step", {"stage": "search", "text": "Searching trusted sources..."})
    raw = await asyncio.to_thread(websearch.search_evidence, claim.get("search_query", ""), claim.get("claim_text", ""))
    yield sse("step", {"stage": "search_done", "text": f"Found {len(raw)} sources."})

    yield sse("step", {"stage": "context", "text": "Analyzing evidence stance..."})
    ctx = await asyncio.to_thread(context_builder.build_context, claim.get("claim_text", ""), raw)
    yield sse("step", {"stage": "context_done",
                       "text": f"Evidence: {ctx['supporting_count']} supporting · {ctx['contradicting_count']} contradicting · {ctx['neutral_count']} neutral"})

    yield sse("step", {"stage": "tot", "text": "Tree-of-Thought verification (4 branches)..."})
    final = None
    gen = verification_graph.tot_steps(claim.get("claim_text", ""), claim.get("search_query", ""),
                                       ctx["evidence"], pg, forgery=forgery)

    def _next(g):
        try: return next(g)
        except StopIteration: return None

    while True:
        item = await asyncio.to_thread(_next, gen)
        if item is None: break
        name, payload = item
        if name == "legal":
            if payload.get("is_legal"):
                yield sse("step", {"stage": "legal", "text": f"Legal claim — consulted BNS/IPC/Constitution ({payload.get('count',0)} sections)."})
        elif name in _BRANCH:
            yield sse("branch", {"name": _BRANCH[name], "score": round(payload.get("score", 0.0), 2)})
        elif name == "reflection":
            ap = payload.get("approved", True)
            yield sse("step", {"stage": "reflection", "text": f"Reflection (LLM-as-judge): {'approved' if ap else 'adjusted'} — {payload.get('note','')}"})
        elif name == "verdict":
            final = payload

    ev_card = [{"title": e.get("title", ""), "url": e.get("url", ""), "source_type": e.get("source_type", "web"),
                "snippet": e.get("snippet", ""), "stance": e.get("stance", "neutral")} for e in ctx["evidence"][:5]]
    for le in (final.get("legal_evidence") or [])[:2]:
        ev_card.append({"title": le.get("title", "Indian Law"), "url": "", "source_type": "legal", "snippet": le.get("snippet", ""), "stance": "neutral"})
    verdict = {"verdict": final["verdict"], "confidence": final["confidence"], "summary": final["summary"],
               "evidence": ev_card, "branches": final.get("branches", {}), "is_legal": final.get("is_legal", False),
               "needs_human_review": final.get("needs_human_review", False), "reflection": final.get("reflection", {}), "forgery": final.get("forgery")}
    async for c in _type_out(final["summary"]): yield c
    memory.set_last_verdict(session_id, verdict, claim_text=claim.get("claim_text", ""), input_type=input_type)
    memory.add_message(session_id, "assistant", final["summary"])
    if config.DB_ENABLED:
        db.log_stage(session_id, "full_pipeline", (time.time() - _t0) * 1000, "success")
    yield sse("verdict", verdict); yield sse("done", {})


async def pipeline(session_id, message, input_type, file_bytes, filename):
    if not config.llm_ready():
        yield sse("step", {"stage": "config", "text": "Checking configuration..."})
        await asyncio.sleep(0.3)
        msg = ("No Gemini API key found. Add GEMINI_API_KEY_1..6 to your .env and restart. "
               "Free keys: https://aistudio.google.com/apikey")
        async for c in _type_out(msg): yield c
        yield sse("done", {}); return

    if input_type == "audio" and file_bytes:
        memory.add_message(session_id, "user", f"(audio: {filename})")
        yield sse("step", {"stage": "audio", "text": f"Transcribing audio: {filename}..."})
        res = await asyncio.to_thread(audio_service.transcribe, file_bytes, filename)
        if not res["ok"]:
            async for c in _type_out("Sorry — " + res["error"]): yield c
            yield sse("done", {}); return
        yield sse("step", {"stage": "audio_done", "text": f"Transcript: \"{res['text'][:80]}\""})
        async for ev in _run_claim(session_id, res["text"], input_type="audio"): yield ev
        return

    if input_type == "image" and file_bytes:
        memory.add_message(session_id, "user", f"(image: {filename})")
        yield sse("step", {"stage": "image", "text": f"Analyzing image: {filename} (OCR + vision + forensics)..."})
        res = await asyncio.to_thread(image_service.analyze, file_bytes, filename)
        if not res["ok"]:
            async for c in _type_out("Sorry — " + res["error"]): yield c
            yield sse("done", {}); return
        if res.get("ocr_text"):
            yield sse("step", {"stage": "ocr", "text": f"OCR text: \"{res['ocr_text'][:70]}\""})
        if res.get("vision"):
            yield sse("step", {"stage": "vision", "text": "Vision: " + res["vision"][:90]})
        fg = res.get("forgery") or {}
        if fg and fg.get("label") != "not_checked":
            reasons = "; ".join(fg.get("reasons", [])[:2])
            yield sse("step", {"stage": "forgery", "text": f"Forensics: {fg.get('label')} ({int(fg.get('confidence',0)*100)}%) — {reasons}"})
        if not res["claim_seed"]:
            if fg.get("label") == "likely_edited":
                summary = "This image shows signs of editing/manipulation. " + "; ".join(fg.get("reasons", [])[:3])
                async for c in _type_out(summary): yield c
                v = {"verdict": "Manipulated", "confidence": fg.get("confidence", 0.6), "summary": summary, "evidence": [], "forgery": fg, "needs_human_review": True}
                memory.set_last_verdict(session_id, v, claim_text="(image)", input_type="image")
                memory.add_message(session_id, "assistant", summary)
                yield sse("verdict", v)
            else:
                async for c in _type_out("I couldn't read a verifiable claim from this image."): yield c
            yield sse("done", {}); return
        async for ev in _run_claim(session_id, res["claim_seed"], forgery=fg, input_type="image"): yield ev
        return

    memory.add_message(session_id, "user", message or "(text)")
    yield sse("step", {"stage": "router", "text": "Understanding your message..."})
    has_prev = memory.has_verdict(session_id)
    intent = (await asyncio.to_thread(router_agent.route, message, has_prev))["intent"]

    if intent == "chat":
        yield sse("step", {"stage": "chat", "text": "Composing a reply..."})
        reply = await asyncio.to_thread(chat_agent.casual_reply, message, memory.get_history(session_id))
        async for c in _type_out(reply): yield c
        memory.add_message(session_id, "assistant", reply); yield sse("done", {}); return

    if intent == "follow_up":
        yield sse("step", {"stage": "follow_up", "text": "Looking back at the previous result..."})
        reply = await asyncio.to_thread(chat_agent.follow_up_reply, message, memory.get_last_verdict(session_id))
        async for c in _type_out(reply): yield c
        memory.add_message(session_id, "assistant", reply); yield sse("done", {}); return

    async for ev in _run_claim(session_id, message): yield ev


@router.post("/chat")
async def chat(session_id: str = Form(...), message: str = Form(""),
               input_type: str = Form("text"), file: Optional[UploadFile] = File(None)):
    file_bytes = await file.read() if file is not None else None
    filename = file.filename if file is not None else ""
    return StreamingResponse(pipeline(session_id, message, input_type, file_bytes, filename),
                             media_type="text/event-stream")


@router.post("/reset")
async def reset(session_id: str = Form(...)):
    memory.reset(session_id)
    return {"status": "ok"}


# ---------------- chat history (NEW) ----------------
@router.get("/sessions")
def sessions():
    """Recent chats for the sidebar."""
    return {"sessions": db.list_sessions(30)}


@router.get("/sessions/{session_id}")
def session_detail(session_id: str):
    """Full chat (messages + verdicts) to reopen an old conversation."""
    data = db.get_session_full(session_id)
    # warm the in-process cache so follow-ups work after reopening
    lv = data["verdicts"][-1] if data["verdicts"] else None
    if lv:
        memory.set_last_verdict(session_id, lv)
    return data
