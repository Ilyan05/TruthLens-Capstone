from collections import defaultdict, deque
from backend import config, db

_h = defaultdict(lambda: deque(maxlen=config.MEMORY_WINDOW))   # RAM cache for speed
_lv = {}                                                       # last verdict cache


def add_message(session_id, role, content):
    _h[session_id].append({"role": role, "content": content})
    if config.DB_ENABLED:
        db.touch_session(session_id)
        db.add_message(session_id, role, content)


def get_history(session_id):
    # prefer RAM; if empty (e.g. after restart), load from DB
    if _h.get(session_id):
        return list(_h[session_id])
    if config.DB_ENABLED:
        rows = db.get_messages(session_id, config.MEMORY_WINDOW)
        for r in rows:
            _h[session_id].append(r)
        return rows
    return []


def set_last_verdict(session_id, v, claim_text="", input_type="text"):
    _lv[session_id] = v
    if config.DB_ENABLED and v.get("verdict"):
        try:
            db.save_verdict(session_id, claim_text or v.get("summary", "")[:120], input_type, v)
        except Exception:
            pass


def get_last_verdict(session_id):
    return _lv.get(session_id)


def has_verdict(session_id):
    return session_id in _lv


def reset(session_id):
    _h.pop(session_id, None)
    _lv.pop(session_id, None)
