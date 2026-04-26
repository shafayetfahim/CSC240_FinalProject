import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class BillCategorizer:
    def __init__(self, n_clusters=5):
        self.n_clusters = n_clusters
        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        self.kmeans = KMeans(n_clusters=self.n_clusters, random_state=42)

    def categorize_bills(self, input_csv="../data/new_data/congressional_votes_cleaned.csv", output_csv="../data/new_data/bills_categorized.csv"):
        """Applies TF-IDF and K-Means to normalize bill intent."""
        try:
            df = pd.read_csv(input_csv)
            df['Summary'] = df['Summary'].fillna(df['Title']) 
            
            logging.info("Extracting features using TF-IDF...")
            X = self.vectorizer.fit_transform(df['Summary'])
            
            logging.info("Clustering bills into categories...")
            df['Category_Label'] = self.kmeans.fit_predict(X)
            
            df.to_csv(output_csv, index=False)
            logging.info(f"Categorization complete. Saved to {output_csv}")
            return df
        except Exception as e: logging.error(f"Error in NLP Pipeline: {e}")

if __name__ == "__main__":
    nlp = BillCategorizer()
    nlp.categorize_bills(
        input_csv="../data/new_data/congressional_votes_cleaned.csv",
        output_csv="../data/new_data/bills_categorized.csv"
    )