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

    # #Phase 1: data Ingestion
    # logging.info("--- PHASE 1: INGESTION ---")
    # congress_miner = CongressMiner()
    #
    # #Unleashing the miner with maximum API efficiency!
    # congress_miner.fetch_members(limit=250, max_pages=3)
    #
    # #Maxing out the bills in a single request
    # congress_miner.fetch_bills(congress=118, limit=250)

    #Phase 2: NLP Categorization (UPDATED FOR NEW FILES!!!!)
    logging.info("--- PHASE 2: NLP CATEGORIZATION ---")
    categorizer = BillCategorizer(n_clusters=5)
    categorizer.categorize_bills(input_csv="../data/new_data/congressional_votes_cleaned.csv", output_csv="../data/new_data/bills_categorized.csv")

    df = categorizer.categorize_bills(
        input_csv="../data/new_data/congressional_votes_cleaned.csv",
        output_csv="../data/new_data/bills_categorized.csv"
    )

    # --- NEW: Visualization Step ---
    logging.info("--- PHASE 2.2: VISUALIZATION ---")
    from bills_visualizer import BillClusterVisualizer

    viz = BillClusterVisualizer(categorizer.vectorizer, categorizer.kmeans)
    viz.visualize(df)

    #Phase 2.5: Build the Receipts (Turned ON for this run only)
    #logging.info("--- PHASE 2.5: FETCHING REAL VOTING DATA ---")
    #fetch_real_receipts(rep_limit=535) # <-- The critical fix!

    # Phase 3: Association Rule Mining
    logging.info("--- PHASE 3: APRIORI MINING ---")
    apriori_miner = AprioriMiner(min_support=0.05) 
    
    # 1. Build the one-hot encoded matrix
    basket = apriori_miner.build_transactions("../data/new_data/voting_history.csv")
    
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
        history_df = pd.read_csv("../data/new_data/voting_history.csv")
        reps_df = pd.read_csv("../data/new_data/member_ideology_cleaned.csv")

        # Merge voting history with party affiliation
        merged_df = pd.merge(history_df, reps_df[['icpsr', 'party_code']], on='icpsr', how='inner')

        # Encode categorical data for the decision tree
        le = LabelEncoder()
        merged_df['party_code'] = le.fit_transform(merged_df['party_code'])

        # Define features (X) and target (y)
        #X = merged_df[['Category_Label', 'party_code']]
       # y = merged_df['Voted_Yes']

        # Keep icpsr for tracking, but don't train the model on it
        X_features = merged_df[['Category_Label', 'party_code']]
        X_tracking = merged_df[['icpsr']]
        y = merged_df['Voted_Yes']

        # 2. Apply Chronological Holdout
        evaluator = ChronologicalEvaluator()
        X_train, X_val, X_test = evaluator.split_data(X_features)
        X_test_tracking = evaluator.split_data(X_tracking)[2]  # Get the icpsrs for the test set
        y_train, y_val, y_test = evaluator.split_data(y)

        # 3. Train the BOAT Proxy Model
        classifier = BoatClassifierProxy()
        model = classifier.train_model(X_train, y_train)

        # 4. Predict the Tie-Breakers on the Test Set
        logging.info("Predicting tie-breaker votes on the test set...")
        predictions = classifier.predict_outcome(X_test)

        majority_baseline = y.value_counts(normalize=True).max()

        predictions = classifier.predict_outcome(X_test)

        #NEW: Run the classifier and find the errors
        # Create a dataframe to compare reality vs. the model's partisan guess
        results_df = X_test_tracking.copy()
        results_df['Actual_Vote'] = y_test
        results_df['Predicted_Vote'] = predictions

        # Find where the legislator defied the partisan expectation
        results_df['Defected'] = results_df['Actual_Vote'] != results_df['Predicted_Vote']

        # Group by Legislator to find the top Tie-Breaker candidates
        tie_breakers = results_df.groupby('icpsr')['Defected'].mean().sort_values(ascending=False)

        results_df.to_csv("../data/new_data/results.csv", index=False)

        logging.info("Top Legislator Candidates for 'Tie-Breakers' (Highest Defection Rates):")
        logging.info(tie_breakers.head(10))


        # 5. Evaluate the Results
        logging.info("--- PHASE 5: EVALUATION METRICS ---")
        evaluator.evaluate_model(y_test, predictions, majority_baseline)

        # Determine attribute strength
        importance = classifier.get_feature_importance(X_features.columns)
        logging.info(f"Attribute Strength (Gini): {importance}")

    except Exception as e:
        logging.error(f"Classification failed: {e}")

    logging.info("Sprint Pipeline Complete!")


if __name__ == "__main__":
    run_sprint_pipeline()