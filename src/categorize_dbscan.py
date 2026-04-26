import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class BillCategorizer:
    def __init__(self, eps=0.7, min_samples=5):
        self.eps = eps
        self.min_samples = min_samples

        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=2000,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.85
        )

        self.dbscan = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            metric='cosine'   # important for text!
        )

    def categorize_bills(self, input_csv="../data/bills_data.csv", output_csv="../data/bills_categorized.csv"):
        """Applies TF-IDF and DBSCAN clustering to group bills."""
        try:
            df = pd.read_csv(input_csv)

            # Fill missing summaries
            df['Summary'] = df['Summary'].fillna(df['Title'])

            logging.info("Extracting features using TF-IDF...")
            x = self.vectorizer.fit_transform(df['Summary'])

            # Normalize for better cosine distance behavior
            #X = normalize(X)

            logging.info("Clustering bills using DBSCAN...")
            labels = self.dbscan.fit_predict(x)


            df['Category_Label'] = labels

            df.to_csv(output_csv, index=False)
            logging.info(f"Categorization complete. Saved to {output_csv}")

            return df

        except Exception as e:
            logging.error(f"Error in NLP Pipeline: {e}")


if __name__ == "__main__":
    nlp = BillCategorizer(eps=0.7, min_samples=5)
    nlp.categorize_bills()