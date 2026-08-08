"""
TruthLens - LLM Layer (Gemini via LangChain) with API KEY ROTATION.
"""

import time
import json
import re
import itertools

from backend import config


_clients = {}
_key_cycle = None


def _keys():
    ks = getattr(config, "GEMINI_API_KEYS", None) or []

    return [
        k for k in ks
        if k and "paste_your" not in k
    ]


def _cycle():
    global _key_cycle

    if _key_cycle is None:
        _key_cycle = itertools.cycle(_keys())

    return _key_cycle


def _get_client(model_name, api_key):
    kid = f"{model_name}::{api_key[-6:]}"

    if kid in _clients:
        return _clients[kid]

    from langchain_google_genai import ChatGoogleGenerativeAI

    c = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=config.LLM_TEMPERATURE
    )

    _clients[kid] = c

    return c


def _content_to_text(resp):
    content = getattr(resp, "content", resp)

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        p = []

        for b in content:
            if isinstance(b, str):
                p.append(b)

            elif isinstance(b, dict):
                p.append(
                    b.get("text")
                    or b.get("content")
                    or ""
                )

        return "".join(p)

    if isinstance(content, dict):
        return content.get("text") or str(content)

    return str(content)


def _is_rate_limit(e):
    s = str(e).lower()

    return (
        "429" in s
        or "rate" in s
        or "quota" in s
        or "resource_exhausted" in s
    )


def _is_not_found(e):
    s = str(e).lower()

    return (
        "404" in s
        or "not_found" in s
        or "not found" in s
    )


def llm_ready():
    return len(_keys()) > 0


def call_llm(prompt, reasoning=False):
    keys = _keys()

    if not keys:
        raise RuntimeError(
            "No Gemini API key set. Add GEMINI_API_KEY_1..N to .env"
        )

    primary = (
        config.MODEL_REASONING
        if reasoning
        else config.MODEL_FAST
    )

    models = [
        primary
    ] + [
        m for m in getattr(config, "FALLBACK_MODELS", [])
        if m != primary
    ]

    last = None

    for model in models:
        for _ in range(len(keys)):
            key = next(_cycle())

            try:
                client = _get_client(model, key)

            except Exception as e:
                last = e
                continue

            for attempt in range(config.LLM_MAX_RETRIES):
                try:
                    resp = client.invoke(prompt)
                    time.sleep(config.RATE_DELAY)

                    return _content_to_text(resp)

                except Exception as e:
                    last = e

                    if _is_rate_limit(e):
                        break

                    if _is_not_found(e):
                        break

                    if attempt < config.LLM_MAX_RETRIES - 1:
                        time.sleep(config.LLM_RETRY_BACKOFF)
                        continue

                    break

            if last and _is_not_found(last):
                break

    raise last if last else RuntimeError("LLM call failed")


def call_llm_vision(
    prompt,
    image_bytes,
    mime="image/jpeg",
    reasoning=True
):
    import base64

    keys = _keys()

    if not keys:
        raise RuntimeError("No Gemini API key set.")

    model = (
        config.MODEL_REASONING
        if reasoning
        else config.MODEL_FAST
    )

    b64 = base64.b64encode(image_bytes).decode()

    msg = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": f"data:{mime};base64,{b64}"
                }
            ]
        }
    ]

    last = None

    for _ in range(len(keys)):
        key = next(_cycle())

        try:
            client = _get_client(model, key)
            resp = client.invoke(msg)
            time.sleep(config.RATE_DELAY)

            return _content_to_text(resp)

        except Exception as e:
            last = e

            if _is_rate_limit(e):
                continue

            raise

    raise last if last else RuntimeError("vision call failed")


def _extract_json(text):
    if not text or not isinstance(text, str):
        return None

    text = re.sub(
        r"```(?:json)?",
        "",
        text
    ).strip("` \n")

    m = re.search(
        r"(\{.*\}|\[.*\])",
        text,
        re.DOTALL
    )

    cand = m.group(1) if m else text

    try:
        return json.loads(cand)

    except Exception:
        return None


def call_llm_json(prompt, reasoning=False, default=None):
    raw = call_llm(
        prompt,
        reasoning=reasoning
    )

    parsed = _extract_json(raw)

    if parsed is None:
        return (
            default
            if default is not None
            else {
                "_raw": raw,
                "_parse_error": True
            }
        )

    return parsed