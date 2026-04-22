# import logging
# import pandas as pd
# from ingest import CongressMiner
# from categorize import BillCategorizer
# from mine import AprioriMiner
# from evaluate import ChronologicalEvaluator
# from classify import BoatClassifierProxy
# from sklearn.preprocessing import LabelEncoder
# from real_voting_history import fetch_real_receipts

# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# def run_sprint_pipeline():
#     logging.info("Starting the Tie-Breaker Pipeline...")

#     #Phase 1: Data Ingestion
#     logging.info("--- PHASE 1: INGESTION ---")
#     congress_miner = CongressMiner()
    
#     #Unleashing the miner with maximum API efficiency!
#     congress_miner.fetch_members(limit=250, max_pages=3) 
    
#     #Maxing out the bills in a single request
#     congress_miner.fetch_bills(congress=118, limit=250)
    
#     #Phase 2: NLP Categorization
#     logging.info("--- PHASE 2: NLP CATEGORIZATION ---")
#     categorizer = BillCategorizer(n_clusters=5)
#     categorizer.categorize_bills(input_csv="../data/bills_data.csv", output_csv="../data/bills_categorized.csv")

#     #Phase 2.5: Build the Receipts (Turned ON for this run only)
#     logging.info("--- PHASE 2.5: FETCHING REAL VOTING DATA ---")
#     fetch_real_receipts(rep_limit=535) # <-- The critical fix!

#     # Phase 3: Association Rule Mining
#     logging.info("--- PHASE 3: APRIORI MINING ---")
#     apriori_miner = AprioriMiner(min_support=0.05) 
    
#     # 1. Build the one-hot encoded matrix
#     basket = apriori_miner.build_transactions("../data/voting_history.csv")
    
#     if basket is not None:
#         # 2. Mine for common voting patterns
#         rules = apriori_miner.mine_patterns(basket)
        
#         # 3. Display the top logical rules found
#         if not rules.empty:
#             logging.info("Top 5 Voting Coalitions/Patterns Found:")
#             top_rules = rules.sort_values(by='lift', ascending=False).head(5)
#             for index, row in top_rules.iterrows():
#                 logging.info(f"Rule: IF supports {set(row['antecedents'])} THEN supports {set(row['consequents'])} (Lift: {row['lift']:.2f})")
#         else: logging.warning("No strong patterns found. Try lowering min_support.")

#     logging.info("Pipeline executed successfully. Awaiting Phase 4 (BOAT Classification).")

#     # Phase 4: BOAT Classification & Evaluation
#     logging.info("--- PHASE 4: BOAT CLASSIFICATION ---")
    
#     try:
#         # 1. Load the merged data
#         history_df = pd.read_csv("../data/voting_history.csv")
#         reps_df = pd.read_csv("../data/representatives_cleaned.csv")
        
#         # Merge voting history with party affiliation
#         merged_df = pd.merge(history_df, reps_df[['UID', 'party_code']], on='UID', how='inner')
        
#         # Encode categorical data for the decision tree
#         le = LabelEncoder()
#         merged_df['party_code'] = le.fit_transform(merged_df['party_code'])
        
#         # Define features (X) and target (y)
#         X = pd.get_dummies(merged_df, columns=['Category_Label'])[['party_code'] + [col for col in merged_df.columns if 'Category_Label' in col]]
#         y = merged_df['Voted_Yes']
        
#         # 2. Apply Chronological Holdout
#         evaluator = ChronologicalEvaluator()
#         X_train, X_val, X_test = evaluator.split_data(X)
#         y_train, y_val, y_test = evaluator.split_data(y)
        
#         # 3. Train the BOAT Proxy Model
#         classifier = BoatClassifierProxy()
#         model = classifier.train_model(X_train, y_train)
        
#         # 4. Predict the Tie-Breakers on the Test Set
#         logging.info("Predicting tie-breaker votes on the test set...")
#         predictions = classifier.predict_outcome(X_test)
        
#         majority_baseline = y.value_counts(normalize=True).max()
        
#         # 5. Evaluate the Results
#         logging.info("--- PHASE 5: EVALUATION METRICS ---")
#         evaluator.evaluate_model(y_test, predictions, majority_baseline)
        
#         # Determine attribute strength
#         importance = classifier.get_feature_importance(X.columns)
#         logging.info(f"Attribute Strength (Gini): {importance}")

#     except Exception as e: logging.error(f"Classification failed: {e}")

#     logging.info("Sprint Pipeline Complete!")

# if __name__ == "__main__":
#     run_sprint_pipeline()

import logging
import pandas as pd
import os

# Import your custom modules
from ingest import CongressMiner
from categorize import BillCategorizer
from mine import AprioriMiner
from evaluate import ChronologicalEvaluator
from classify import BoatClassifierProxy
from features import engineer_political_features
from real_voting_history import fetch_real_receipts

# Set up professional logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("pipeline.log"), logging.StreamHandler()]
)

def run_sprint_pipeline():
    logging.info("Starting the Production-Grade Legislative Pipeline...")

    # --- PHASE 1: BULK INGESTION ---
    # We target 10,000 bills to maximize statistical resolution
    logging.info("--- PHASE 1: INGESTION ---")
    miner = CongressMiner()
    # miner.fetch_members(limit=250, max_pages=3)
    # miner.fetch_bills(congress=118, target=10000)

    # --- PHASE 2: NLP CATEGORIZATION ---
    logging.info("--- PHASE 2: NLP CATEGORIZATION ---")
    # Increased to 10 clusters to account for 10,000 bills
    categorizer = BillCategorizer(n_clusters=10)
    # categorizer.categorize_bills()

    # --- PHASE 2.5: MULTITHREADED RECEIPTS ---
    logging.info("--- PHASE 2.5: VOTING HISTORY RETRIEVAL ---")
    # This maps the 10,000 bills to the 535 representatives
    # fetch_real_receipts(rep_limit=535)

    # --- PHASE 3: ASSOCIATION RULE MINING ---
    logging.info("--- PHASE 3: APRIORI COALITION ANALYSIS ---")
    miner_apriori = AprioriMiner(min_support=0.05)
    basket = miner_apriori.build_transactions("../data/voting_history.csv")
    if basket is not None:
        rules = miner_apriori.mine_patterns(basket)
        top_rules = rules.sort_values('lift', ascending=False).head(5)
        logging.info(f"Top Voting Coalitions Found:\n{top_rules[['antecedents', 'consequents', 'lift']]}")

    # --- PHASE 4: CLASSIFICATION (The BOAT Model) ---
    logging.info("--- PHASE 4: BOAT CLASSIFICATION ---")
    try:
        # 1. Load Data
        history_df = pd.read_csv("../data/voting_history.csv")
        reps_df = pd.read_csv("../data/representatives_cleaned.csv")
        
        # 2. Merge and Initial Clean
        merged_df = pd.merge(history_df, reps_df[['UID', 'party', 'party_code', 'state']], on='UID')

        # 3. Chronological Split (BEFORE Encoding to prevent Leakage)
        evaluator = ChronologicalEvaluator()
        train_df, test_df = evaluator.split_data(merged_df)

        # 4. Feature Engineering (Representation Models)
        # Calculates party_expected and state_expected using Train data only
        train_df, test_df = engineer_political_features(train_df, test_df)

        # 5. One-Hot Encoding (Solving the Integer Trap)
        # We concat and dummies to ensure train/test columns match perfectly
        full_df = pd.concat([train_df, test_df], sort=False)
        full_df = pd.get_dummies(full_df, columns=['Category_Label'], prefix='Topic')
        
        train_final = full_df.iloc[:len(train_df)].copy()
        test_final = full_df.iloc[len(train_df):].copy()

        # 6. Define Feature Set
        topic_cols = [col for col in full_df.columns if col.startswith('Topic_')]
        features = ['party_expected', 'state_expected'] + topic_cols
        
        # 7. Train the Model
        classifier = BoatClassifierProxy()
        classifier.train_model(train_final[features], train_final['Voted_Yes'])
        
        # 8. Predict and Evaluate
        logging.info("Predicting tie-breaker behavior on Test Set...")
        predictions = classifier.predict_outcome(test_final[features])
        
        # --- PHASE 5: EVALUATION ---
        logging.info("--- PHASE 5: FINAL EVALUATION ---")
        evaluator.evaluate_model(test_final['Voted_Yes'], predictions)

        # 9. Attribute Strength Analysis
        importance = classifier.get_feature_importance(features)
        logging.info(f"Final Model Attribute Strengths: {importance}")

    except Exception as e:
        logging.error(f"Classification Pipeline Failed: {e}")

    logging.info("Full Pipeline Execution Complete.")

if __name__ == "__main__":
    run_sprint_pipeline()