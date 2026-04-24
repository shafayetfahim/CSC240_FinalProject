# ingestion.py
# CSC240
# Aiden Hughes, Mahathir Khan, Shafayet Fahim

import requests
import csv
import time
import logging
from typing import Optional, Tuple
import config

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class CongressMiner:
    def __init__(self):
        self.api_key = config.API_KEY
        self.base_url = config.BASE_URL
        self.output_members = "../data/representatives_cleaned.csv"
        self.output_bills = "../data/bills_data.csv"
        self.common_params = {
            'api_key': self.api_key,
            'format': 'json'
        }

    """
    Categorizes party affilitation. Should we change Libertarian to just broadly Third-Party?
    """
    def normalize_party(self, party_name: Optional[str]) -> str:
        if not party_name: return "Unknown"
        mapping = {"Democratic": "D", "Republican": "R", "Libertarian": "L"}
        return mapping.get(party_name, "Other")
    
    """
    Serializes name into first and last during fetch_members() call.
    """
    def split_name(self, name: str) -> Tuple[str, str]:
        if "," in name:
            parts = name.split(",", 1)
            return parts[0].strip(), parts[1].strip()
        return name, ""

    """
    API GET: Representative data + IDs. 
    """
    def fetch_members(self, limit: int = 100, max_pages: int = 10):
        """Fetches representative metadata with a hard limit for testing/pagination."""
        try:
            with open(self.output_members, 'w', newline='', encoding='utf-8') as f:
                import csv
                import time
                import requests
                
                writer = csv.writer(f)
                writer.writerow(['UID', 'lastName', 'firstName', 'state', 'party', 'party_code', 'district'])
                
                url = f"{self.base_url}/member"
                params = {**self.common_params, 'limit': limit}
                
                page_count = 0 # Initialize our tracker
                
                # The loop now checks TWO conditions: Is there a URL? AND Have we hit our limit?
                while url and page_count < max_pages:
                    logging.info(f"Mining members from page {page_count + 1}...")
                    response = requests.get(url, params=params)
                    response.raise_for_status()
                    data = response.json()
                    
                    for m in data.get('members', []):
                        last, first = self.split_name(m.get('name', ""))
                        writer.writerow([
                            m.get('bioguideId'),
                            last,
                            first,
                            m.get('state'),
                            m.get('partyName'),
                            self.normalize_party(m.get('partyName')),
                            m.get('district', 0)
                        ])
                    
                    # Look for the next page link
                    url = data.get('pagination', {}).get('next')
                    params = {'api_key': self.api_key} 
                    page_count += 1 # Increment the tracker
                    time.sleep(0.1) # Rate limiting protection
                    
            logging.info(f"Member ingestion stopped. Reached {page_count} pages.")
        except Exception as e:
            logging.error(f"Error fetching members: {e}")
    """
    API Get: Bill data + IDs.
    """
    def fetch_bills(self, congress: int = 118, limit: int = 250):
        """
        Fetches up to 2,000 bills by paginating through the API.
        We use the 250-limit rule and increment the offset.
        """
        total_needed = 2000
        current_offset = 0
        all_bills = []
        
        logging.info(f"Starting ingestion for {total_needed} bills...")

        try:
            while len(all_bills) < total_needed:
                params = {
                    'api_key': self.api_key,
                    'format': 'json',
                    'limit': limit, # This is 250
                    'offset': current_offset
                }
                
                url = f"{self.base_url}/bill/{congress}"
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                bills_in_page = data.get('bills', [])
                if not bills_in_page:
                    break # Stop if we run out of bills before hitting 2,000
                
                for b in bills_in_page:
                    # Logic to fetch the summary for each bill
                    # (Your existing summary fetching code goes here)
                    # For brevity, let's assume we collect the IDs
                    all_bills.append(b)
                
                logging.info(f"Mined {len(all_bills)} bills so far (Offset: {current_offset})")
                
                # Turn the page
                current_offset += limit
                time.sleep(0.1) # Protect your API key from being throttled
            
            # Save all 2,000 bills to your CSV
            # (Your existing CSV writer logic goes here)
            
        except Exception as e:
            logging.error(f"Bill ingestion failed: {e}")
        """
        Fetches up to 2,000 bills by paginating through the API.
        We use the 250-limit rule and increment the offset.
        """
        total_needed = 2000
        current_offset = 0
        all_bills = []
        
        logging.info(f"Starting ingestion for {total_needed} bills...")

        try:
            while len(all_bills) < total_needed:
                params = {
                    'api_key': self.api_key,
                    'format': 'json',
                    'limit': limit, # This is 250
                    'offset': current_offset
                }
                
                url = f"{self.base_url}/bill/{congress}"
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                bills_in_page = data.get('bills', [])
                if not bills_in_page:
                    break # Stop if we run out of bills before hitting 2,000
                
                for b in bills_in_page:
                    # Logic to fetch the summary for each bill
                    # (Your existing summary fetching code goes here)
                    # For brevity, let's assume we collect the IDs
                    all_bills.append(b)
                
                logging.info(f"Mined {len(all_bills)} bills so far (Offset: {current_offset})")
                
                # Turn the page
                current_offset += limit
                time.sleep(0.1) # Protect your API key from being throttled
            
            # Save all 2,000 bills to your CSV
            # (Your existing CSV writer logic goes here)
            
        except Exception as e:
            logging.error(f"Bill ingestion failed: {e}")
        try:
            with open(self.output_bills, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['BillID', 'Type', 'Title', 'Status', 'Summary'])
                
                url = f"{self.base_url}/bill/{congress}"
                params = {**self.common_params, 'limit': limit}
                
                response = requests.get(url, params=params)
                response.raise_for_status()
                bills = response.json().get('bills', [])

                for bill in bills:
                    bill_type = bill.get('type', 'hr').lower()
                    bill_number = bill.get('number')
                    summary_url = f"{self.base_url}/bill/{congress}/{bill_type}/{bill_number}/summaries"
                    summary_response = requests.get(summary_url, params=self.common_params)
                    summary_text = ""
                    if summary_response.status_code == 200:
                        summaries = summary_response.json().get('summaries', [])
                        if summaries: summary_text = summaries[0].get('text', "")

                    writer.writerow([
                        f"{congress}-{bill_type}{bill_number}",
                        bill_type,
                        bill.get('title'),
                        bill.get('latestAction', {}).get('text'),
                        summary_text
                    ])
                    logging.info(f"Mined Summary for Bill {bill_number}")
                    time.sleep(0.1)
        except Exception as e: logging.error(f"Error fetching bills: {e}")

if __name__ == "__main__":
    miner = CongressMiner()
    logging.info("INGESTION: RUNNING...")
    miner.fetch_members(limit=100)
    miner.fetch_bills(congress=118, limit=50)
    logging.info("INGESTION: COMPLETE.")