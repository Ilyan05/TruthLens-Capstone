import os
import sqlite3
import json
import time
from backend import config

_conn = None


def _get():
    global _conn
    if _conn is not None:
        return _conn
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _init(_conn)
    return _conn


def _init(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY, title TEXT, created_at REAL, last_active REAL
    );
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
        role TEXT, content TEXT, timestamp REAL
    );
    CREATE TABLE IF NOT EXISTS verdicts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
        claim_text TEXT, input_type TEXT, verdict TEXT, confidence REAL,
        summary TEXT, needs_human_review INTEGER, is_legal INTEGER,
        forgery_json TEXT, evidence_json TEXT, created_at REAL
    );
    CREATE TABLE IF NOT EXISTS evidence (
        id INTEGER PRIMARY KEY AUTOINCREMENT, verdict_id INTEGER,
        title TEXT, url TEXT, source_type TEXT, stance TEXT, snippet TEXT
    );
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
        stage TEXT, duration_ms INTEGER, status TEXT, timestamp REAL
    );
    """)
    conn.commit()


# ---------------- sessions ----------------
def touch_session(session_id, title=None):
    if not config.DB_ENABLED:
        return
    c = _get(); now = time.time()
    c.execute("INSERT INTO sessions (id, title, created_at, last_active) VALUES (?,?,?,?) "
              "ON CONFLICT(id) DO UPDATE SET last_active=?", (session_id, title, now, now, now))
    if title:
        # set title only if it's still empty
        c.execute("UPDATE sessions SET title=? WHERE id=? AND (title IS NULL OR title='')",
                  (title, session_id))
    c.commit()


def list_sessions(limit=30):
    """Recent chats for the sidebar: [{id, title, last_active, last_verdict}]"""
    if not config.DB_ENABLED:
        return []
    c = _get()
    rows = c.execute("SELECT id, title, last_active FROM sessions "
                     "ORDER BY last_active DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        v = c.execute("SELECT verdict FROM verdicts WHERE session_id=? "
                      "ORDER BY id DESC LIMIT 1", (r["id"],)).fetchone()
        out.append({"id": r["id"], "title": r["title"] or "New verification",
                    "last_active": r["last_active"],
                    "last_verdict": v["verdict"] if v else None})
    return out


def get_session_full(session_id):
    """Full chat for reopening: messages + verdicts (with evidence/forgery)."""
    if not config.DB_ENABLED:
        return {"messages": [], "verdicts": []}
    c = _get()
    msgs = [{"role": r["role"], "content": r["content"]}
            for r in c.execute("SELECT role, content FROM messages WHERE session_id=? "
                               "ORDER BY id ASC", (session_id,)).fetchall()]
    verdicts = []
    for r in c.execute("SELECT * FROM verdicts WHERE session_id=? ORDER BY id ASC",
                       (session_id,)).fetchall():
        verdicts.append({
            "claim_text": r["claim_text"], "verdict": r["verdict"],
            "confidence": r["confidence"], "summary": r["summary"],
            "needs_human_review": bool(r["needs_human_review"]),
            "is_legal": bool(r["is_legal"]),
            "forgery": json.loads(r["forgery_json"]) if r["forgery_json"] else None,
            "evidence": json.loads(r["evidence_json"]) if r["evidence_json"] else [],
        })
    return {"messages": msgs, "verdicts": verdicts}


# ---------------- messages ----------------
def add_message(session_id, role, content):
    if not config.DB_ENABLED:
        return
    c = _get()
    c.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES (?,?,?,?)",
              (session_id, role, content, time.time()))
    c.commit()


def get_messages(session_id, limit=10):
    if not config.DB_ENABLED:
        return []
    c = _get()
    rows = c.execute("SELECT role, content FROM messages WHERE session_id=? "
                     "ORDER BY id DESC LIMIT ?", (session_id, limit)).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


# ---------------- verdicts + evidence ----------------
def save_verdict(session_id, claim_text, input_type, v):
    if not config.DB_ENABLED:
        return None
    c = _get()
    cur = c.execute(
        "INSERT INTO verdicts (session_id, claim_text, input_type, verdict, confidence, "
        "summary, needs_human_review, is_legal, forgery_json, evidence_json, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (session_id, claim_text, input_type, v.get("verdict", ""),
         float(v.get("confidence", 0.0)), v.get("summary", ""),
         1 if v.get("needs_human_review") else 0, 1 if v.get("is_legal") else 0,
         json.dumps(v.get("forgery")) if v.get("forgery") else None,
         json.dumps(v.get("evidence") or []), time.time()))
    vid = cur.lastrowid
    for e in (v.get("evidence") or []):
        c.execute("INSERT INTO evidence (verdict_id, title, url, source_type, stance, snippet) "
                  "VALUES (?,?,?,?,?,?)",
                  (vid, e.get("title", ""), e.get("url", ""), e.get("source_type", ""),
                   e.get("stance", ""), e.get("snippet", "")))
    c.commit()
    return vid


# ---------------- logs ----------------
def log_stage(session_id, stage, duration_ms, status="success"):
    if not config.DB_ENABLED:
        return
    c = _get()
    c.execute("INSERT INTO logs (session_id, stage, duration_ms, status, timestamp) VALUES (?,?,?,?,?)",
              (session_id, stage, int(duration_ms), status, time.time()))
    c.commit()


# ---------------- metrics ----------------
def get_metrics():
    if not config.DB_ENABLED:
        return {"enabled": False}
    c = _get()
    total = c.execute("SELECT COUNT(*) n FROM verdicts").fetchone()["n"]
    by_verdict = {r["verdict"]: r["n"] for r in
                  c.execute("SELECT verdict, COUNT(*) n FROM verdicts GROUP BY verdict").fetchall()}
    by_input = {r["input_type"]: r["n"] for r in
                c.execute("SELECT input_type, COUNT(*) n FROM verdicts GROUP BY input_type").fetchall()}
    review = c.execute("SELECT COUNT(*) n FROM verdicts WHERE needs_human_review=1").fetchone()["n"]
    legal = c.execute("SELECT COUNT(*) n FROM verdicts WHERE is_legal=1").fetchone()["n"]
    manip = c.execute("SELECT COUNT(*) n FROM verdicts WHERE verdict='Manipulated'").fetchone()["n"]
    avg_conf = c.execute("SELECT AVG(confidence) a FROM verdicts").fetchone()["a"] or 0
    stages = {r["stage"]: round(r["a"] or 0) for r in
              c.execute("SELECT stage, AVG(duration_ms) a FROM logs GROUP BY stage").fetchall()}
    fails = c.execute("SELECT COUNT(*) n FROM logs WHERE status='failed'").fetchone()["n"]
    total_logs = c.execute("SELECT COUNT(*) n FROM logs").fetchone()["n"] or 1
    return {"enabled": True, "total_checks": total, "by_verdict": by_verdict,
            "by_input": by_input, "human_review_rate": round(review / total, 3) if total else 0,
            "legal_claims": legal, "manipulated_detected": manip,
            "avg_confidence": round(avg_conf, 3), "avg_latency_ms_per_stage": stages,
            "success_rate": round(1 - fails / total_logs, 3)}
