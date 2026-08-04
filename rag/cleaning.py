from pathlib import Path
import json
import re


def clean_csv_to_json(input_file, output_file):
    cleaned_data = []
    seen = set()

    with open(input_file, "r", encoding="latin1", errors="ignore") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            # Match CSV format:
            # id,title,image_url,source,tag,date,label
            pattern = r'^([^,]+),(.*?),(https?://.*?),(.*?),(.*?),(.*?),(.*?)$'

            match = re.search(pattern, line, re.IGNORECASE)

            if match:
                news_id = match.group(1).strip()
                title = match.group(2).strip()
                image_url = match.group(3).strip()
                source = match.group(4).strip().upper()
                tag = match.group(5).strip().upper()
                date = match.group(6).strip()
                label = match.group(7).strip().capitalize()

                record = {
                    "id": news_id,
                    "title": title,
                    "image_url": image_url,
                    "source": source,
                    "tag": tag,
                    "date": date,
                    "label": label
                }

                # Remove duplicate records
                key = (news_id, title)

                if key not in seen:
                    seen.add(key)
                    cleaned_data.append(record)

    # Save cleaned data as JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            cleaned_data,
            f,
            indent=4,
            ensure_ascii=False
        )

    print(f"Total Records: {len(cleaned_data)}")
    print(f"JSON Saved: {output_file}")


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent

    input_file = BASE_DIR.parent / "data" / "IFND.csv"
    output_file = BASE_DIR.parent / "data" / "IFND_cleaned.json"

    clean_csv_to_json(input_file, output_file)