# Libraries
import requests
import csv
import time
import config

# Dataset
DATASET_FILE = "representatives.csv"

# Normalize name input
def clean_member_name(raw_name):
    if "," not in raw_name: return raw_name, ""
    last_name, first_middle = raw_name.split(",", 1)
    first_middle_parts = first_middle.strip().split(" ")
    first_name = first_middle_parts[0]
    return last_name.strip(), first_name.strip()

# Fetch from api.congress.gov
def fetch_congress_dataset():
    base_url = f"{config.BASE_URL}/member"
    params = {
        'api_key': config.API_KEY,
        'format': 'json',
        'limit': 538}

    with open(DATASET_FILE, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['lastName', 'firstName', 'UID', 'state', 'party', 'district'])
        current_url = base_url
        
        while current_url:
            print(f"Fetching: {current_url}")
            response = requests.get(current_url, params=params)
            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                break
            data = response.json()
            members = data.get('members', [])

            for m in members:
                raw_name = m.get('name', "")
                last_name, first_name = clean_member_name(raw_name)
                writer.writerow([
                    last_name,
                    first_name,
                    m.get('bioguideId'),
                    m.get('state'),
                    m.get('partyName'),
                    m.get('district'),
                ])
            current_url = data.get('pagination', {}).get('next')
            params = {}
            time.sleep(0.1)
    print(f"Fetch complete.")

# Driver
if __name__ == "__main__":
    fetch_congress_dataset()