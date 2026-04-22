import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
import logging

class AprioriMiner:
    def __init__(self, min_support=0.1):
        self.min_support = min_support

    def build_transactions(self, voting_record_csv="voting_history.csv"):
        """
        Converts voting history into a one-hot encoded format suitable for Apriori.
        Expects a CSV with columns: UID, Category_Label, Voted_Yes (1 or 0).
        """
        try:
            df = pd.read_csv(voting_record_csv)
            supported = df[df['Voted_Yes'] == 1]
            
            basket = (supported.groupby(['UID', 'Category_Label'])['Voted_Yes']
                      .sum().unstack().reset_index().fillna(0)
                      .set_index('UID'))
            
            
            basket_sets = basket.map(lambda x: True if x > 0 else False)
            return basket_sets
        except Exception as e:
            logging.error(f"Transaction build error: {e}")
            return None

    def mine_patterns(self, basket_sets):
        """Applies the Apriori algorithm to find frequent voting categories."""
        frequent_itemsets = apriori(basket_sets, min_support=self.min_support, use_colnames=True)
        rules = association_rules(frequent_itemsets, metric="lift", min_threshold=1.0)
        logging.info(f"Found {len(rules)} association rules.")
        return rules

if __name__ == "__main__":
    miner = AprioriMiner()
    # Note: Requires a merged dataset of representatives and categorized bills
    # basket = miner.build_transactions("merged_voting_data.csv")
    # if basket is not None:
    #     rules = miner.mine_patterns(basket)