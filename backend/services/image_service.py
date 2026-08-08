"""
Image Service (Phase 5 + 6): OCR + Vision + Forgery.
"""

from backend import config, llm
from backend.services import forgery_service

def _ext_ok(filename):
    ext = (filename.rsplit(".", 1)[-1] or "").lower()
    return ext in config.IMAGE_FORMATS, ext

def _mime(ext):
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png"
    }.get(ext, "image/jpeg")

def _ocr(image_bytes):
    try:
        import io
        from PIL import Image
        import pytesseract

        return (
            pytesseract.image_to_string(
                Image.open(io.BytesIO(image_bytes))
            ) or ""
        ).strip()

    except Exception:
        return ""

def _vision(image_bytes, ext):
    prompt = (
        "Look at this image. In 2-3 sentences, describe what it shows. "
        "Then, if there is any readable text (headline, caption, poster), "
        "quote it.\n\n"
        "Format:\n"
        "DESCRIPTION: ...\n"
        "TEXT: ..."
    )

    try:
        return llm.call_llm_vision(
            prompt,
            image_bytes,
            mime=_mime(ext),
            reasoning=True
        ).strip()

    except Exception:
        return ""


def analyze(image_bytes, filename):
    ok, ext = _ext_ok(filename)

    if not ok:
        return {
            "ok": False,
            "error": (
                f"Unsupported image .{ext}. "
                f"Allowed: {sorted(config.IMAGE_FORMATS)}"
            )
        }

    if len(image_bytes) > config.IMAGE_MAX_MB * 1024 * 1024:
        return {
            "ok": False,
            "error": f"Image too large (> {config.IMAGE_MAX_MB} MB)."
        }

    ocr_text = _ocr(image_bytes)
    vision = _vision(image_bytes, ext)

    claim_seed = (
        ocr_text
        if len(ocr_text) >= 15
        else vision
    )

    forgery = forgery_service.analyze_forgery(image_bytes)

    return {
        "ok": True,
        "error": "",
        "ocr_text": ocr_text,
        "vision": vision,
        "claim_seed": claim_seed or "",
        "forgery": forgery
    }