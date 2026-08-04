import easyocr
from backend.preprocessing.text_cleaner import clean_text
import warnings
warnings.filterwarnings("ignore")

reader = easyocr.Reader(['en'])

def extract_text_from_image(image_path):
    result = reader.readtext(image_path)
    extracted_text = " ".join(
        [item[1] for item in result]
    )
    return clean_text(extracted_text)