"""Session Memory (in-process, Phase 2). Phase 7 swaps to SQLite."""
from collections import defaultdict, deque
from backend import config

_history = defaultdict(lambda: deque(maxlen=config.MEMORY_WINDOW))
_last_verdict = {}

def add_message(session_id, role, content):
    _history[session_id].append({"role": role, "content": content})

def get_history(session_id):
    return list(_history.get(session_id, []))

def set_last_verdict(session_id, verdict):
    _last_verdict[session_id] = verdict

def get_last_verdict(session_id):
    return _last_verdict.get(session_id)

def has_verdict(session_id):
    return session_id in _last_verdict

def reset(session_id):
    _history.pop(session_id, None)
    _last_verdict.pop(session_id, None)
