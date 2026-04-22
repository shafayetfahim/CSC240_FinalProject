import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def generate_proxy_votes(reps_csv="../data/representatives_cleaned.csv", 
                         bills_csv="../data/bills_categorized.csv", 
                         output_csv="../data/voting_history.csv"):
    """
    Generates a proxy voting history to test the Apriori and BOAT algorithms.
    Maps real UIDs to real Bill Categories with randomized voting behavior.
    """
    try:
        logging.info("Loading real UIDs and Bill Categories...")
        reps = pd.read_csv(reps_csv)
        bills = pd.read_csv(bills_csv)
        
        # We need a subset of Reps so the Apriori matrix isn't too sparse for testing
        test_reps = reps['UID'].dropna().sample(n=100, random_state=42).tolist()
        categories = bills['Category_Label'].unique().tolist()
        
        history = []
        logging.info("Simulating voting receipts for Market Basket Analysis...")
        
        for uid in test_reps:
            for cat in categories:
                # Simulate a 60% chance they voted 'Yes' on a bill in this category
                voted_yes = np.random.choice([0, 1], p=[0.4, 0.6])
                history.append({'UID': uid, 'Category_Label': cat, 'Voted_Yes': voted_yes})
                
        df_history = pd.DataFrame(history)
        df_history.to_csv(output_csv, index=False)
        logging.info(f"Proxy voting history saved to {output_csv}")
        
    except Exception as e:
        logging.error(f"Data merge failed: {e}")

if __name__ == "__main__":
    generate_proxy_votes()