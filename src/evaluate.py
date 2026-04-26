from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score
from scipy.stats import binomtest
import logging

class ChronologicalEvaluator:
    @staticmethod
    def split_data(df):
        """
        Partitions data sequentially by vote date: 70% Train, 15% Val, 15% Test.
        Assumes df is already sorted chronologically by date.
        """
        n = len(df)
        train_end = int(n * 0.70)
        val_end = int(n * 0.85)

        train = df.iloc[:train_end]
        val = df.iloc[train_end:val_end]
        test = df.iloc[val_end:]
        
        logging.info(f"Chronological Split: Train({len(train)}), Val({len(val)}), Test({len(test)})")
        return train, val, test

    @staticmethod
    def evaluate_model(y_true, y_pred, majority_class_baseline):
        """
        Evaluates prioritizing F1 and calculating statistical significance.
        """
        acc = accuracy_score(y_true, y_pred)
        f1 = f1_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred)
        recall = recall_score(y_true, y_pred)
        
        # Calculate p-value against the Majority Class Baseline
        successes = int(acc * len(y_true))
        p_value = binomtest(successes, len(y_true), majority_class_baseline, alternative='greater').pvalue
        
        metrics = {
            "Accuracy": acc,
            "F1-Score": f1,
            "Precision": precision,
            "Recall": recall,
            "P-Value": p_value
        }
        
        for k, v in metrics.items():
            logging.info(f"{k}: {v:.4f}")
            
        if p_value < 0.05: logging.info("Result is statistically significant (p < 0.05).")
        else: logging.warning("Result failed statistical significance threshold.")
            
        return metrics