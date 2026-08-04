from backend.preprocessing.validator import validate_file
from backend.preprocessing.metadata import get_metadata
from backend.preprocessing.image_processor import extract_text_from_image
from backend.preprocessing.audio_processor import transcribe_audio

def preprocess(file_path):
    file_type = validate_file(file_path)
    if file_type == "text":
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        result = {
            "content_type": "text",
            "text": content
        }

    elif file_type == "image":
        text = extract_text_from_image(file_path)
        result = {
            "content_type": "image",
            "text": text
        }
        
    elif file_type == "audio":
        transcript = transcribe_audio(file_path)
        result = {
            "content_type": "audio",
            "text": transcript
    }
    result["metadata"] = get_metadata(file_path)
    return result