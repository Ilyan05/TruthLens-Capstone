import re

def clean_text(text):
    text = text.lower()
    # Keep only alphabets and spaces
    text = re.sub(r'[^a-zA-Z\s]', ' ', text)
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()