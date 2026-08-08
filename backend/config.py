"""TruthLens - Central Configuration (single source of truth)."""
import os
from dotenv import load_dotenv
load_dotenv()

# ---------------- API KEYS (rotation: up to 6 group members) ----------------
GEMINI_API_KEYS = [os.getenv(f"GEMINI_API_KEY_{i}", "") for i in range(1, 7)]
_single = os.getenv("GEMINI_API_KEY", "")
if _single:
    GEMINI_API_KEYS.append(_single)
GEMINI_API_KEYS = [k for k in GEMINI_API_KEYS if k and "paste_your" not in k]
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""

# ---------------- MODELS (hybrid) ----------------
MODEL_REASONING = "gemini-3.5-flash"
MODEL_FAST = "gemini-3.5-flash-lite"
FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest"]

# ---------------- LLM SETTINGS ----------------
LLM_TEMPERATURE = 0.0
RATE_DELAY = 1.0
LLM_MAX_RETRIES = 3
LLM_RETRY_BACKOFF = 2.5

# ---------------- FACT-CHECK RULES ----------------
FASTPATH_CONFIDENCE = 0.95
MIN_CONFIDENCE = 0.65
MIN_SOURCES = 2
HIGH_RISK_TOPICS = ["politics", "election", "health", "medical",
                    "legal", "religion", "violence", "finance"]

# ---------------- TREE OF THOUGHT ----------------
TOT_MODE = "two_stage"
TOT_WEIGHTS = {"evidence": 0.50, "source": 0.25, "context": 0.15, "pregrounder": 0.10}
REFLECTION_ENABLED = True

# ---------------- LEGAL RAG ----------------
LEGAL_RAG_ENABLED = True
LEGAL_DIR = "data/legal"
LEGAL_DB_DIR = "data/legal_chroma"
LEGAL_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LEGAL_CHUNK_SIZE = 600
LEGAL_CHUNK_OVERLAP = 80
LEGAL_TOP_K = 4
LEGAL_TRIGGERS = ["anti-national", "antinational", "sedition", "treason",
                  "unconstitutional", "illegal", "constitution", "fundamental right",
                  "article ", "ipc", "bns", "penal code", "nyaya sanhita",
                  "law says", "against the law", "punishable", "defamation",
                  "hate speech", "contempt"]

# ---------------- MEMORY ----------------
MEMORY_WINDOW = 10

# ---------------- AUDIO / IMAGE ----------------
AUDIO_MODE = "gemini"
AUDIO_FORMATS = {"mp3", "wav", "m4a", "ogg", "webm"}   # webm = browser live-mic recording
AUDIO_MAX_MB = 25
IMAGE_FORMATS = {"jpg", "jpeg", "png"}
IMAGE_MAX_MB = 10

# ---------------- FORGERY (PHASE 6) ----------------
FORGERY_ENABLED = True
FORGERY_MODEL_PATH = "models/forgery_model.h5"
FORGERY_CNN_THRESHOLD = 0.5
ELA_QUALITY = 90
ELA_FLAG_THRESHOLD = 18.0
EDIT_SOFTWARE_TAGS = ["photoshop", "gimp", "lightroom", "snapseed", "paint",
                      "pixlr", "canva", "affinity", "coreldraw"]

# ---------------- VERDICT LABELS ----------------
VERDICT_LABELS = ["Real", "Fake", "Misleading", "Manipulated", "Inconclusive"]

# ---------------- WEB SEARCH ----------------
SEARCH_MAX_RESULTS = 8
SEARCH_PER_SOURCE = 4
WIKI_SENTENCES = 3
INDIA_NEWS_SITES = ["thehindu.com", "indianexpress.com", "timesofindia.com",
                    "hindustantimes.com", "ndtv.com", "livemint.com",
                    "theprint.in", "reuters.com"]
FACTCHECK_SITES = ["altnews.in", "boomlive.in", "factly.in",
                   "vishvasnews.com", "pib.gov.in", "snopes.com"]

# ---------------- DB / PATHS ----------------
DB_PATH = "data/truthlens.db"
FRONTEND_DIR = "frontend"
METRICS_ENABLED = True

# ---------------- PHASE 7: PERSISTENCE / OBSERVABILITY ----------------
DB_ENABLED = True                 # SQLite persistence (sessions/messages/verdicts/evidence/logs)
# LangSmith tracing — set these in .env to enable (zero code change):
#   LANGCHAIN_TRACING_V2=true
#   LANGCHAIN_API_KEY=ls__your_key
#   LANGCHAIN_PROJECT=truthlens
LANGSMITH_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"
LEGAL_DISCLAIMER = ("Note: This references Indian law (BNS 2023 / Constitution; "
                    "IPC 1860 for older cases) for context only and is not legal advice.")


def llm_ready() -> bool:
    return len(GEMINI_API_KEYS) > 0
