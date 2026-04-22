import logging
import pandas as pd
from ingest import CongressMiner
from categorize import BillCategorizer
from mine import AprioriMiner
from evaluate import ChronologicalEvaluator
from classify import BoatClassifierProxy
from sklearn.preprocessing import LabelEncoder
from real_voting_history import fetch_real_receipts

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_sprint_pipeline():
    logging.info("Starting the Tie-Breaker Pipeline...")

    #Phase 1: Data Ingestion
    logging.info("--- PHASE 1: INGESTION ---")
    congress_miner = CongressMiner()
    
    #Unleashing the miner with maximum API efficiency!
    congress_miner.fetch_members(limit=250, max_pages=3) 
    
    #Maxing out the bills in a single request
    congress_miner.fetch_bills(congress=118, limit=250)
    
    #Phase 2: NLP Categorization
    logging.info("--- PHASE 2: NLP CATEGORIZATION ---")
    categorizer = BillCategorizer(n_clusters=5)
    categorizer.categorize_bills(input_csv="../data/bills_data.csv", output_csv="../data/bills_categorized.csv")

    #Phase 2.5: Build the Receipts (Turned ON for this run only)
    logging.info("--- PHASE 2.5: FETCHING REAL VOTING DATA ---")
    fetch_real_receipts(rep_limit=535) # <-- The critical fix!

    # Phase 3: Association Rule Mining
    logging.info("--- PHASE 3: APRIORI MINING ---")
    apriori_miner = AprioriMiner(min_support=0.05) 
    
    # 1. Build the one-hot encoded matrix
    basket = apriori_miner.build_transactions("../data/voting_history.csv")
    
    if basket is not None:
        # 2. Mine for common voting patterns
        rules = apriori_miner.mine_patterns(basket)
        
        # 3. Display the top logical rules found
        if not rules.empty:
            logging.info("Top 5 Voting Coalitions/Patterns Found:")
            top_rules = rules.sort_values(by='lift', ascending=False).head(5)
            for index, row in top_rules.iterrows():
                logging.info(f"Rule: IF supports {set(row['antecedents'])} THEN supports {set(row['consequents'])} (Lift: {row['lift']:.2f})")
        else: logging.warning("No strong patterns found. Try lowering min_support.")

    logging.info("Pipeline executed successfully. Awaiting Phase 4 (BOAT Classification).")

    # Phase 4: BOAT Classification & Evaluation
    logging.info("--- PHASE 4: BOAT CLASSIFICATION ---")
    
    try:
        # 1. Load the merged data
        history_df = pd.read_csv("../data/voting_history.csv")
        reps_df = pd.read_csv("../data/representatives_cleaned.csv")
        
        # Merge voting history with party affiliation
        merged_df = pd.merge(history_df, reps_df[['UID', 'party_code']], on='UID', how='inner')
        
        # Encode categorical data for the decision tree
        le = LabelEncoder()
        merged_df['party_code'] = le.fit_transform(merged_df['party_code'])
        
        # Define features (X) and target (y)
        X = merged_df[['Category_Label', 'party_code']]
        y = merged_df['Voted_Yes']
        
        # 2. Apply Chronological Holdout
        evaluator = ChronologicalEvaluator()
        X_train, X_val, X_test = evaluator.split_data(X)
        y_train, y_val, y_test = evaluator.split_data(y)
        
        # 3. Train the BOAT Proxy Model
        classifier = BoatClassifierProxy()
        model = classifier.train_model(X_train, y_train)
        
        # 4. Predict the Tie-Breakers on the Test Set
        logging.info("Predicting tie-breaker votes on the test set...")
        predictions = classifier.predict_outcome(X_test)
        
        majority_baseline = y.value_counts(normalize=True).max()
        
        # 5. Evaluate the Results
        logging.info("--- PHASE 5: EVALUATION METRICS ---")
        evaluator.evaluate_model(y_test, predictions, majority_baseline)
        
        # Determine attribute strength
        importance = classifier.get_feature_importance(X.columns)
        logging.info(f"Attribute Strength (Gini): {importance}")

    except Exception as e: logging.error(f"Classification failed: {e}")

    logging.info("Sprint Pipeline Complete!")

if __name__ == "__main__":
    run_sprint_pipeline()