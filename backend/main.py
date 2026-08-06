"""
TruthLens - FastAPI App (single-terminal: serves BOTH API + frontend)
Run:  python run.py   ->  http://localhost:8000
"""
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.routers import chat
from backend import config

app = FastAPI(title="TruthLens API", version="0.3.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(chat.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "TruthLens API", "phase": 3,
            "llm_configured": config.llm_ready()}


FRONTEND = config.FRONTEND_DIR


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
