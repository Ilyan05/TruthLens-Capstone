
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------- API KEYS ----------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ---------------- MODELS (hybrid strategy) ----------------
# NOTE: Google retired the 2.5-lite for new users; using Gemini 3.5 family.
MODEL_REASONING = "gemini-3.5-flash"        # reasoning-heavy
MODEL_FAST = "gemini-3.5-flash-lite"        # speed-heavy

# Fallback models (auto-tried in order if primary returns 404 NOT_FOUND)
FALLBACK_MODELS = [
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
]

# ---------------- LLM SETTINGS ----------------
LLM_TEMPERATURE = 0.0
RATE_DELAY = 1.0               # seconds between LLM calls (free-tier safety)
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

# ---------------- MEMORY ----------------
MEMORY_WINDOW = 10

# ---------------- AUDIO ----------------
AUDIO_MODE = "gemini"
AUDIO_FORMATS = {"mp3", "wav", "m4a", "ogg"}
AUDIO_MAX_MB = 25

# ---------------- IMAGE ----------------
IMAGE_FORMATS = {"jpg", "jpeg", "png"}
IMAGE_MAX_MB = 10
FORGERY_MODEL_PATH = "models/forgery_model.h5"

# ---------------- VERDICT LABELS ----------------
VERDICT_LABELS = ["Real", "Fake", "Misleading", "Manipulated", "Inconclusive"]

# ---------------- WEB SEARCH ----------------
SEARCH_MAX_RESULTS = 8          # total evidence items to keep
SEARCH_PER_SOURCE = 4           # results per source group
SEARCH_TIMEOUT = 12             # seconds budget for the whole search step
WIKI_SENTENCES = 3              # summary length from Wikipedia
INDIA_NEWS_SITES = [
    "thehindu.com", "indianexpress.com", "timesofindia.com",
    "hindustantimes.com", "ndtv.com", "livemint.com",
    "theprint.in", "reuters.com",
]
FACTCHECK_SITES = [
    "altnews.in", "boomlive.in", "factly.in",
    "vishvasnews.com", "pib.gov.in", "snopes.com",
]

# ---------------- DATABASE ----------------
DB_PATH = "data/truthlens.db"

# ---------------- PATHS ----------------
FRONTEND_DIR = "frontend"

# ---------------- METRICS ----------------
METRICS_ENABLED = True


def llm_ready() -> bool:
    return bool(GEMINI_API_KEY and GEMINI_API_KEY != "paste_your_gemini_api_key_here")
