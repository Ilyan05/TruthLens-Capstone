import base64
from backend import config, llm
def _ext_ok(fn):
    ext=(fn.rsplit(".",1)[-1] or "").lower();return ext in config.AUDIO_FORMATS,ext
def _mime(ext):return {"mp3":"audio/mp3","wav":"audio/wav","m4a":"audio/mp4","ogg":"audio/ogg","webm":"audio/webm"}.get(ext,"audio/mpeg")
def _gemini(audio_bytes,ext):
    b64=base64.b64encode(audio_bytes).decode()
    msg=[{"role":"user","content":[{"type":"text","text":"Transcribe this audio to plain text. Return ONLY the spoken words."},{"type":"media","mime_type":_mime(ext),"data":b64}]}]
    keys=llm._keys();model=config.MODEL_FAST;last=None
    for _ in range(max(1,len(keys))):
        key=next(llm._cycle())
        try:return llm._content_to_text(llm._get_client(model,key).invoke(msg)).strip()
        except Exception as e:
            last=e
            if llm._is_rate_limit(e):continue
            raise
    raise last if last else RuntimeError("transcription failed")
def _whisper(path):
    import whisper
    return whisper.load_model("base").transcribe(path)["text"].strip()
def transcribe(audio_bytes,filename):
    ok,ext=_ext_ok(filename)
    if not ok:return {"ok":False,"text":"","error":f"Unsupported audio .{ext}. Allowed: {sorted(config.AUDIO_FORMATS)}"}
    if len(audio_bytes)>config.AUDIO_MAX_MB*1024*1024:return {"ok":False,"text":"","error":f"Audio too large (> {config.AUDIO_MAX_MB} MB)."}
    if config.AUDIO_MODE=="gemini":
        try:
            t=_gemini(audio_bytes,ext)
            if t:return {"ok":True,"text":t,"error":""}
            gerr="empty transcript"
        except Exception as e:gerr=str(e)
        try:
            import tempfile,os
            with tempfile.NamedTemporaryFile(suffix="."+ext,delete=False) as f:f.write(audio_bytes);tmp=f.name
            t=_whisper(tmp);os.unlink(tmp)
            if t:return {"ok":True,"text":t,"error":""}
        except Exception:pass
        return {"ok":False,"text":"","error":"Transcription failed. "+gerr[:120]}
    try:
        import tempfile,os
        with tempfile.NamedTemporaryFile(suffix="."+ext,delete=False) as f:f.write(audio_bytes);tmp=f.name
        t=_whisper(tmp);os.unlink(tmp);return {"ok":True,"text":t,"error":""}
    except Exception as e:return {"ok":False,"text":"","error":"Whisper failed: "+str(e)[:120]}
