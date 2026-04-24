import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
import logging

class BoatClassifierProxy:
    def __init__(self):
        # We use 'balanced' to implement the weighted penalty system
        # This prioritizes rare defecting votes over vast party loyalty
        self.clf = DecisionTreeClassifier(
            criterion='gini', # Using Gini Index to quantify attribute strength
            class_weight='balanced',
            random_state=42,
            max_depth=5 # Prevent overfitting initially
        )

    def train_model(self, X_train, y_train):
        """Trains the decision tree on historical partisan data."""
        logging.info("Training classification tree with weighted penalties...")
        self.clf.fit(X_train, y_train)
        return self.clf

    def predict_outcome(self, X_test):
        """Predicts whether the representative will cosponsor."""
        return self.clf.predict(X_test)

    def get_feature_importance(self, feature_names):
        """Returns the strength of attributes (e.g., bill content, party)."""
        return dict(zip(feature_names, self.clf.feature_importances_))