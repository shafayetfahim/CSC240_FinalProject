import os
import requests
import pandas as pd
import time
import config

# Configuration
HEADERS = {"x-api-key": config.API_KEY, "Content-Type": "application/json"}
BASE_URL = "https://api.congress.gov/v3"
OUTPUT_DIR = "outputs"

def get_bills(congress, limit=250):
    """Fetches list of bills from a specific congress."""
    all_bills = []
    offset = 0
    while len(all_bills) < limit:
        url = f"{BASE_URL}/bill/{congress}?limit=250&offset={offset}&format=json"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            bills = response.json().get('bills', [])
            if not bills: break
            all_bills.extend(bills)
            offset += 250
        else:
            time.sleep(60) 
    return all_bills

def get_vote_details(congress, session, vote_number):
    """Fetches how members voted for a specific roll call."""
    url = f"{BASE_URL}/house-vote/{congress}/{session}/{vote_number}/members"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get('results', [])
    return []

def run_extraction():
    # 1. Ensure the directory exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created directory: {OUTPUT_DIR}")

    # 2. Fetch Bills
    print("Fetching bill metadata...")
    bills = get_bills(118, limit=2000)
    
    data_rows = []
    
    # 3. Iterate through bills and find roll calls
    for bill in bills[:2000]:
        # (Your existing logic here...)
        time.sleep(1.5) 
        
    # 4. Export with the new path
    df = pd.DataFrame(data_rows)
    output_path = os.path.join(OUTPUT_DIR, "congressional_voting_data.csv")
    df.to_csv(output_path, index=False)
    print(f"Extraction complete. File saved to: {output_path}")

if __name__ == "__main__":
    run_extraction()
