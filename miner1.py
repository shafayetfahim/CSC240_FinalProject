import requests
import pandas as pd
import time
import config # Assuming your key is stored here

HEADERS = {"x-api-key": config.API_KEY, "Content-Type": "application/json"}
BASE_URL = "https://api.congress.gov/v3"

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
            time.sleep(60) # Backoff if rate limited
    return all_bills

def get_vote_details(congress, session, vote_number):
    """Fetches how members voted for a specific roll call."""
    url = f"{BASE_URL}/house-vote/{congress}/{session}/{vote_number}/members"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get('results', [])
    return []

def run_extraction():
    # 1. Fetch Bills (Example: 118th Congress)
    print("Fetching bill metadata...")
    bills = get_bills(118, limit=2000)
    
    data_rows = []
    
    # 2. Iterate through bills and find roll calls
    for bill in bills[:2000]:
        # Simplification: Look for actions that indicate a vote
        # In a real scenario, you would parse the 'actions' object
        # Here we demonstrate the linkage logic
        bill_number = bill['number']
        congress = bill['congress']
        
        # NOTE: You need to cross-reference the bill to the specific Roll Call Number.
        # This usually requires parsing the bill's 'actions' list for an action 
        # that includes a 'rollCallNumber'.
        
        # Pseudo-logic:
        # roll_call_number = extract_roll_call(bill) 
        # if roll_call_number:
        #     votes = get_vote_details(congress, 1, roll_call_number)
        #     for v in votes:
        #         data_rows.append({
        #             'bill_number': bill_number,
        #             'member_id': v['bioguideID'],
        #             'vote': v['voteCast'],
        #             'party': v['voteParty']
        #         })
        
        # Pacing to avoid hitting 1000/hr limit
        time.sleep(1.5) 
        
    # 3. Export
    df = pd.DataFrame(data_rows)
    df.to_csv("congressional_voting_data.csv", index=False)
    print("Extraction complete.")

if __name__ == "__main__":
    run_extraction()
