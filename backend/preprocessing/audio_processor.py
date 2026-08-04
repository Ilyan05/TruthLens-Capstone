import whisper
import re
from backend.preprocessing.text_cleaner import clean_text
import warnings
warnings.filterwarnings("ignore")

model = whisper.load_model("base")

def transcribe_audio(audio_path):
    result = model.transcribe(
        audio_path,
        fp16=False,
        language="en"
    )
    return clean_text(result["text"])