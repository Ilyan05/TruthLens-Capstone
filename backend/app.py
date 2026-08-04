"""
TruthLens - FastAPI Backend
----------------------------
Serves the 4 pages (Welcome, Text, Image, Audio) and exposes stub
submission endpoints. Wire your Claim Extraction / Media Forensics /
RAG agents into the TODO sections below when the pipeline is ready.

NOTE: Video is intentionally NOT supported — only text, image, audio.
"""

import uuid
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------
# PATH SETUP
# BASE_DIR -> backend/ folder itself
# ROOT_DIR -> project root (TruthLens-Capstone/)
# FRONTEND_DIR -> where templates/ and static/ live
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"

app = FastAPI(title="TruthLens API", version="0.1.0")

# ---------------------------------------------------------------------
# CORS - allow frontend (even if served from a different port) to call the API
# ---------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # tighten this to your frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------
# STATIC FILES + TEMPLATES
# ---------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")
templates = Jinja2Templates(directory=FRONTEND_DIR / "templates")

# =======================================================================
# PAGE ROUTES  (Welcome + 3 content-type pages)
# =======================================================================

@app.get("/")
async def welcome_page(request: Request):
    return templates.TemplateResponse(request, "welcome.html")


@app.get("/text")
async def text_page(request: Request):
    return templates.TemplateResponse(request, "text.html")


@app.get("/image")
async def image_page(request: Request):
    return templates.TemplateResponse(request, "image.html")


@app.get("/audio")
async def audio_page(request: Request):
    return templates.TemplateResponse(request, "audio.html")


# =======================================================================
# API ROUTES  (stubbed submission endpoints — plug agents in later)
# =======================================================================

@app.post("/api/v1/submissions/text")
async def submit_text(claim_text: str = Form(...)):
    submission_id = str(uuid.uuid4())

    # TODO: hand off `claim_text` to Preprocessing -> Claim Extraction Agent
    #       -> Supervisor Agent pipeline, then persist to `submissions` table.

    return JSONResponse({
        "submission_id": submission_id,
        "content_type": "text",
        "claim_preview": claim_text[:120],
        "status": "queued",
    })


@app.post("/api/v1/submissions/image")
async def submit_image(file: UploadFile = File(...)):
    submission_id = str(uuid.uuid4())
    contents = await file.read()

    # TODO: validate magic bytes (not just extension), save to storage,
    #       hand off to Media Forensics Agent (DL model + metadata/hash check).

    return JSONResponse({
        "submission_id": submission_id,
        "content_type": "image",
        "filename": file.filename,
        "size_bytes": len(contents),
        "status": "queued",
    })


@app.post("/api/v1/submissions/audio")
async def submit_audio(file: UploadFile = File(...)):
    submission_id = str(uuid.uuid4())
    contents = await file.read()

    # TODO: validate magic bytes, save to storage, run Speech-to-Text
    #       (Whisper/Gemini) -> Claim Extraction Agent.

    return JSONResponse({
        "submission_id": submission_id,
        "content_type": "audio",
        "filename": file.filename,
        "size_bytes": len(contents),
        "status": "queued",
    })


@app.get("/health")
async def health():
    return {"status": "running"}
