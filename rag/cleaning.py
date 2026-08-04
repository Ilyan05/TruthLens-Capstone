from pathlib import Path
import pandas as pd
import json

# edit coming..............

def clean_csv_to_json(input_file, output_file):
    # Load CSV
    df = pd.read_csv(
        input_file,
        encoding="latin1",
        on_bad_lines="skip"
    )

    print("CSV Columns Found:")
    print(df.columns.tolist())

    # Rename columns if your CSV has different names
    # Change these according to printed column names if needed
    column_mapping = {
        "Statement": "title",
        "Image": "image_url",
        "Web": "source",
        "Category": "tag",
        "Date": "date",
        "Label": "label"
    }

    df = df.rename(columns=column_mapping)

    # Required columns for our cleaned JSON
    required_columns = ["title", "label"]

    # Check missing columns
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        print("Missing required columns:", missing_columns)
        print("Available columns are:", df.columns.tolist())
        return

    # If optional columns are missing, create them
    optional_columns = ["id", "image_url", "source", "tag", "date"]

    for col in optional_columns:
        if col not in df.columns:
            df[col] = ""

    # Create id if not available
    if df["id"].isnull().all() or df["id"].astype(str).str.strip().eq("").all():
        df["id"] = range(1, len(df) + 1)

    # Keep final columns
    final_columns = [
        "id",
        "title",
        "image_url",
        "source",
        "tag",
        "date",
        "label"
    ]

    df = df[final_columns]

    # Clean data
    df["id"] = df["id"].astype(str).str.strip()
    df["title"] = df["title"].astype(str).str.strip()
    df["image_url"] = df["image_url"].astype(str).str.strip()
    df["source"] = df["source"].astype(str).str.upper().str.strip()
    df["tag"] = df["tag"].astype(str).str.upper().str.strip()
    df["date"] = df["date"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.capitalize().str.strip()

    # Remove empty title rows
    df = df[df["title"] != ""]
    df = df[df["title"].str.lower() != "nan"]

    # Remove duplicates
    df = df.drop_duplicates(subset=["title"])

    # Convert to list of dictionaries
    records = df.to_dict(orient="records")

    # Save JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4, ensure_ascii=False)

    print(f"Total Records: {len(records)}")
    print(f"JSON Saved: {output_file}")


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent

    input_file = BASE_DIR.parent / "data" / "IFND.csv"
    output_file = BASE_DIR.parent / "data" / "IFND_cleaned.json"

    clean_csv_to_json(input_file, output_file)