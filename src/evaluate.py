# import pandas as pd
# from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score, balanced_accuracy_score
# from scipy.stats import binomtest
# import logging

# class ChronologicalEvaluator:
#     def split_data(self, df):
#         """
#         Partitions data sequentially by vote date: 70% Train, 15% Val, 15% Test.
#         Assumes df is already sorted chronologically by date.
#         """
#         n = len(df)
#         train_end = int(n * 0.70)
#         val_end = int(n * 0.85)

#         train = df.iloc[:train_end]
#         val = df.iloc[train_end:val_end]
#         test = df.iloc[val_end:]
        
#         logging.info(f"Chronological Split: Train({len(train)}), Val({len(val)}), Test({len(test)})")
#         return train, val, test

#     def evaluate_model(self, y_true, y_pred, majority_class_baseline):
#         """
#         Evaluates prioritizing F1 and calculating statistical significance.
#         """
#         acc = accuracy_score(y_true, y_pred)
#         f1 = f1_score(y_true, y_pred)
#         precision = precision_score(y_true, y_pred)
#         recall = recall_score(y_true, y_pred)
        
#         # Calculate p-value against the Majority Class Baseline
#         successes = int(acc * len(y_true))
#         p_value = binomtest(successes, len(y_true), majority_class_baseline, alternative='greater').pvalue
        
#         metrics = {
#             "Accuracy": acc,
#             "F1-Score": f1,
#             "Precision": precision,
#             "Recall": recall,
#             "P-Value": p_value
#         }
        
#         for k, v in metrics.items():
#             logging.info(f"{k}: {v:.4f}")
            
#         if p_value < 0.05:
#             logging.info("Result is statistically significant (p < 0.05).")
#         else:
#             logging.warning("Result failed statistical significance threshold.")
            
#         return metrics

from sklearn.metrics import balanced_accuracy_score, f1_score, precision_score, recall_score
from scipy.stats import binomtest
import logging

class ChronologicalEvaluator:
    def split_data(self, df):
        n = len(df)
        train_end = int(n * 0.70)
        test_df = df.iloc[train_end:].copy()
        train_df = df.iloc[:train_end].copy()
        return train_df, test_df

    def evaluate_model(self, y_true, y_pred):
        """Standardizes evaluation for imbalanced political data."""
        b_acc = balanced_accuracy_score(y_true, y_pred)
        f1 = f1_score(y_true, y_pred)
        rec = recall_score(y_true, y_pred)
        
        # Statistical Test: Is our Balanced Accuracy better than a coin flip (0.5)?
        successes = int(b_acc * len(y_true))
        p_val = binomtest(successes, len(y_true), 0.5, alternative='greater').pvalue
        
        logging.info(f"Balanced Accuracy: {b_acc:.4f}")
        logging.info(f"F1-Score: {f1:.4f}")
        logging.info(f"Recall (Catching 'Yes' votes): {rec:.4f}")
        logging.info(f"P-Value (vs Random): {p_val:.4f}")
        
        if p_val < 0.05:
            logging.info("RESULT: Statistically Significant Pattern Found.")
        else:
            logging.warning("RESULT: No significant departure from random behavior.")