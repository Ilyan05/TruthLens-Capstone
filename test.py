# import csv
# import json
# from agents.claim_extraction import extract_claim

# with open("data/demo_claims.csv") as f:
#     for row in csv.DictReader(f):
#         print(f"\n--- Claim #{row['id']} (expected: {row['expected_label']}) ---")
#         print("Input :", row["text"])
#         result = extract_claim(row["text"])
#         print("Output:", json.dumps(result, indent=2))
import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_FACT_CHECK_KEY")

def search_fact_checks(api_key, query, language_code="en"):
    """
    Searches the Google Fact Check API for a specific topic.
    """
    # The official endpoint for searching claims
    url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    
    # Define parameters according to Google's API specification
    params = {
        "key": api_key,
        "query": query,
        "languageCode": language_code
    }
    
    try:
        response = requests.get(url, params=params)
        # Raise an exception for bad status codes (4xx, 5xx)
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

# --- Example Usage ---
# Replace 'YOUR_API_KEY_HERE' with the key you generated in the Cloud Console
API_KEY = api_key
SEARCH_TERM = "Gautam adani"

data = search_fact_checks(API_KEY, SEARCH_TERM)

if data and "claims" in data:
    print(f"Found {len(data['claims'])} fact-checked claims for '{SEARCH_TERM}':\n")
    
    # Loop through the claims returned by Google
    for claim_item in data["claims"]:
        text = claim_item.get("text", "No text available")
        claimant = claim_item.get("claimant", "Unknown")
        
        # Each claim can have multiple reviews, we grab the first one
        reviews = claim_item.get("claimReview", [])
        if reviews:
            publisher = reviews[0].get("publisher", {}).get("name", "Unknown Publisher")
            title = reviews[0].get("title", "No Title")
            rating = reviews[0].get("textualRating", "No Rating Provided")
            review_url = reviews[0].get("url", "#")
            
            print(f"🔹 Claim: '{text}' by {claimant}")
            print(f"   Fact-Checked By: {publisher}")
            print(f"   Verdict: {rating}")
            print(f"   Source Article: {review_url}")
            print("-" * 50)
else:
    print("No claims found or failed to fetch data.")
