"""
TruthLens - LLM Layer (Gemini via LangChain)
Handles: two model tiers, response normalization (Gemini 3 returns
list-of-blocks), robust JSON parsing, free-tier retry, model fallback.
"""
import time
import json
import re
from backend import config

_clients = {}


def _get_client(model_name: str):
    if model_name in _clients:
        return _clients[model_name]
    from langchain_google_genai import ChatGoogleGenerativeAI
    client = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=config.GEMINI_API_KEY,
        temperature=config.LLM_TEMPERATURE,
    )
    _clients[model_name] = client
    return client


def _content_to_text(resp) -> str:
    """Normalize response (str OR list-of-blocks from Gemini 3) into text."""
    content = getattr(resp, "content", resp)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("text") or block.get("content") or "")
        return "".join(parts)
    if isinstance(content, dict):
        return content.get("text") or str(content)
    return str(content)


def _is_rate_limit(err: Exception) -> bool:
    s = str(err).lower()
    return "429" in s or "rate" in s or "quota" in s or "resource_exhausted" in s


def _is_model_not_found(err: Exception) -> bool:
    s = str(err).lower()
    return "404" in s or "not_found" in s or "not found" in s


def call_llm(prompt: str, reasoning: bool = False) -> str:
    if not config.llm_ready():
        raise RuntimeError("GEMINI_API_KEY not set. Add it to your .env file.")

    primary = config.MODEL_REASONING if reasoning else config.MODEL_FAST
    fallbacks = getattr(config, "FALLBACK_MODELS", [])
    models_to_try = [primary] + [m for m in fallbacks if m != primary]

    last_err = None
    for model in models_to_try:
        try:
            client = _get_client(model)
        except Exception as e:
            last_err = e
            continue
        for attempt in range(config.LLM_MAX_RETRIES):
            try:
                resp = client.invoke(prompt)
                time.sleep(config.RATE_DELAY)
                return _content_to_text(resp)
            except Exception as e:
                last_err = e
                if _is_rate_limit(e) and attempt < config.LLM_MAX_RETRIES - 1:
                    time.sleep(config.LLM_RETRY_BACKOFF * (attempt + 1))
                    continue
                if _is_model_not_found(e):
                    break
                break
    raise last_err if last_err else RuntimeError("LLM call failed")


def _extract_json(text: str):
    if not text or not isinstance(text, str):
        return None
    text = re.sub(r"```(?:json)?", "", text).strip("` \n")
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    candidate = match.group(1) if match else text
    try:
        return json.loads(candidate)
    except Exception:
        return None


def call_llm_json(prompt: str, reasoning: bool = False, default=None):
    raw = call_llm(prompt, reasoning=reasoning)
    parsed = _extract_json(raw)
    if parsed is None:
        return default if default is not None else {"_raw": raw, "_parse_error": True}
    return parsed
