import requests
import pandas as pd
import time
import logging
import concurrent.futures
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

def process_single_rep(uid, bill_cat_map, all_categories):
    """Worker thread: Fetches cosponsorships for one representative."""
    url = f"{config.BASE_URL}/member/{uid}/cosponsored-legislation"
    params = {'api_key': config.API_KEY, 'format': 'json', 'limit': 250}
    
    # Initialize "No" for all categories
    rep_votes = {cat: 0 for cat in all_categories}
    local_history = []
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Check their history against our 2,000 bills
        for cosponsored in data.get('cosponsoredLegislation', []):
            congress = cosponsored.get('congress')
            raw_type = cosponsored.get('type')
            b_type = raw_type.lower() if raw_type else ""
            b_num = cosponsored.get('number')
            target_id = f"{congress}-{b_type}{b_num}"
            
            if target_id in bill_cat_map:
                rep_votes[bill_cat_map[target_id]] = 1
        
        # Format for CSV
        for cat, voted in rep_votes.items():
            local_history.append({'UID': uid, 'Category_Label': cat, 'Voted_Yes': voted})
            
        logging.info(f"Mined receipts for: {uid}")
        return local_history

    except Exception as e:
        logging.warning(f"Skipped {uid}: {e}")
        return []

def fetch_real_receipts(reps_csv="../data/representatives_cleaned.csv", 
                        bills_csv="../data/bills_categorized.csv", 
                        output_csv="../data/voting_history.csv",
                        rep_limit=535):
    try:
        reps_df = pd.read_csv(reps_csv)
        bills_df = pd.read_csv(bills_csv)
        
        bill_cat_map = dict(zip(bills_df['BillID'].str.lower(), bills_df['Category_Label']))
        all_categories = bills_df['Category_Label'].unique().tolist()
        test_reps = reps_df['UID'].dropna().head(rep_limit).tolist()
        
        history = []
        logging.info(f"Starting Multi-threaded fetch for {rep_limit} reps...")
        
        # max_workers=5 keeps us under the 5,000 requests/hr limit safely
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_single_rep, uid, bill_cat_map, all_categories) for uid in test_reps]
            for future in concurrent.futures.as_completed(futures):
                history.extend(future.result())
                # Small throttle to prevent micro-bursting the API
                time.sleep(0.1) 
                
        pd.DataFrame(history).to_csv(output_csv, index=False)
        logging.info(f"Complete matrix saved to {output_csv}")
        
    except Exception as e:
        logging.error(f"Ingestion failed: {e}")