import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from backend.routers import chat
from backend import config
app=FastAPI(title="TruthLens API",version="0.6.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
app.include_router(chat.router)
@app.get("/health")
def health():
    import os
    return {"status":"ok","phase":7,"llm_configured":config.llm_ready(),"keys":len(config.GEMINI_API_KEYS),
            "reflection":config.REFLECTION_ENABLED,"forgery_cnn":os.path.exists(config.FORGERY_MODEL_PATH),
            "db":config.DB_ENABLED,"langsmith":config.LANGSMITH_ENABLED}

@app.get("/api/v1/metrics")
def metrics():
    from backend import db
    return db.get_metrics()

@app.get("/metrics")
def metrics_page():
    import os
    p = os.path.join(config.FRONTEND_DIR, "metrics.html")
    return FileResponse(p) if os.path.exists(p) else {"error": "metrics.html not found"}
@app.get("/")
def index():return FileResponse(os.path.join(config.FRONTEND_DIR,"index.html"))
app.mount("/static",StaticFiles(directory=config.FRONTEND_DIR),name="static")
