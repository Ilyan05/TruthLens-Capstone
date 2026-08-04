from backend.preprocessing.text_cleaner import clean_text

def process_text(text):
    cleaned_text = clean_text(text)
    return {
        "content_type": "text",
        "extracted_text": cleaned_text
    }