import os

ALLOWED_IMAGE = [".jpg", ".jpeg", ".png"]
ALLOWED_AUDIO = [".wav", ".mp3"]
ALLOWED_TEXT = [".txt"]
MAX_SIZE_MB = 25

def validate_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    file_size = os.path.getsize(file_path) / (1024 * 1024)
    if file_size > MAX_SIZE_MB:
        raise ValueError("File too large")
    if ext in ALLOWED_IMAGE:
        return "image"
    if ext in ALLOWED_AUDIO:
        return "audio"
    if ext in ALLOWED_TEXT:
        return "text"
    raise ValueError("Unsupported file type")