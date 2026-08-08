"""Image Forgery Detection (PHASE 6) — ELA + EXIF + CNN, fused into one JSON verdict."""
import io
import os
from backend import config

_cnn_model = None
_cnn_tried = False


# ---------------- 1) ELA ----------------
def _ela_score(image_bytes):
    try:
        from PIL import Image, ImageChops
        orig = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        buf = io.BytesIO()
        orig.save(buf, "JPEG", quality=config.ELA_QUALITY)
        buf.seek(0)
        resaved = Image.open(buf).convert("RGB")
        diff = ImageChops.difference(orig, resaved)
        extrema = diff.getextrema()
        max_diff = max(e[1] for e in extrema) or 1
        total = 0; n = 0
        for r, g, b in diff.getdata():
            total += (r + g + b) / 3; n += 1
        mean = (total / n) * (255.0 / max_diff) if n else 0.0
        return round(mean, 2)
    except Exception:
        return None


# ---------------- 2) EXIF ----------------
def _to_degrees(value):
    try:
        d = float(value[0]); m = float(value[1]); s = float(value[2])
        return d + m / 60.0 + s / 3600.0
    except Exception:
        return None


def _exif(image_bytes):
    out = {"present": False, "software": None, "date": None,
           "camera": None, "gps": None, "edited_software": False}
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
        img = Image.open(io.BytesIO(image_bytes))
        exif = img._getexif() if hasattr(img, "_getexif") else None
        if not exif:
            return out
        out["present"] = True
        gps_raw = {}
        for tag_id, val in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "Software":
                out["software"] = str(val)
                low = str(val).lower()
                out["edited_software"] = any(t in low for t in config.EDIT_SOFTWARE_TAGS)
            elif tag == "DateTimeOriginal" or (tag == "DateTime" and not out["date"]):
                out["date"] = str(val)
            elif tag == "Make":
                out["camera"] = str(val)
            elif tag == "Model":
                out["camera"] = (out.get("camera") or "") + " " + str(val)
            elif tag == "GPSInfo":
                for k, v in val.items():
                    gps_raw[GPSTAGS.get(k, k)] = v
        if gps_raw.get("GPSLatitude") and gps_raw.get("GPSLongitude"):
            lat = _to_degrees(gps_raw["GPSLatitude"]); lon = _to_degrees(gps_raw["GPSLongitude"])
            if lat is not None and lon is not None:
                if gps_raw.get("GPSLatitudeRef") == "S": lat = -lat
                if gps_raw.get("GPSLongitudeRef") == "W": lon = -lon
                out["gps"] = {"lat": round(lat, 5), "lon": round(lon, 5)}
        if out.get("camera"):
            out["camera"] = out["camera"].strip()
    except Exception:
        pass
    return out


# ---------------- 3) CNN ----------------
def _load_cnn():
    global _cnn_model, _cnn_tried
    if _cnn_tried:
        return _cnn_model
    _cnn_tried = True
    if not os.path.exists(config.FORGERY_MODEL_PATH):
        return None
    try:
        import tensorflow as tf
        _cnn_model = tf.keras.models.load_model(config.FORGERY_MODEL_PATH)
    except Exception:
        _cnn_model = None
    return _cnn_model


def _cnn_score(image_bytes):
    model = _load_cnn()
    if model is None:
        return None
    try:
        import numpy as np
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((224, 224))
        arr = np.asarray(img, dtype="float32") / 255.0
        arr = np.expand_dims(arr, 0)
        pred = model.predict(arr, verbose=0)
        p = float(pred.reshape(-1)[0])
        return round(max(0.0, min(1.0, p)), 3)
    except Exception:
        return None


# ---------------- FUSION ----------------
def analyze_forgery(image_bytes):
    if not config.FORGERY_ENABLED:
        return {"label": "not_checked", "confidence": 0.0, "signals": {}, "reasons": ["disabled"]}

    ela = _ela_score(image_bytes)
    exif = _exif(image_bytes)
    cnn = _cnn_score(image_bytes)

    reasons = []; votes = []; ela_flag = None
    if ela is not None:
        ela_flag = ela >= config.ELA_FLAG_THRESHOLD
        votes.append(min(1.0, ela / (config.ELA_FLAG_THRESHOLD * 2)))
        if ela_flag:
            reasons.append(f"ELA high ({ela}) - possible edited regions")
    if exif.get("edited_software"):
        votes.append(0.9)
        reasons.append(f"Editing software in metadata: {exif.get('software')}")
    elif exif.get("present"):
        reasons.append("EXIF metadata present (camera/date/GPS)")
    if cnn is not None:
        votes.append(cnn)
        reasons.append(f"CNN {'flags fake' if cnn >= config.FORGERY_CNN_THRESHOLD else 'flags real'} ({cnn})")

    if not votes:
        return {"label": "not_checked", "confidence": 0.0,
                "signals": {"ela": {"score": ela}, "exif": exif, "cnn": cnn},
                "reasons": ["No forgery signals available"]}

    score = sum(votes) / len(votes)
    label = "likely_edited" if score >= 0.5 else "likely_real"
    if not reasons:
        reasons.append("No strong tampering signals found")

    return {"label": label, "confidence": round(score, 2),
            "signals": {"ela": {"score": ela, "flag": ela_flag}, "exif": exif, "cnn": {"p_fake": cnn}},
            "reasons": reasons}
