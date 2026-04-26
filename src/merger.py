import pandas as pd
import logging

class IdeologyMerger:
    def __init__(self, data_dir="../data/new_data/"):
        self.data_dir = data_dir

    def build_classification_dataset(self, categorized_bills_csv):
        logging.info("Loading DW-NOMINATE ideology and roll-call data...")

        # 1. Load the Data
        ideology_df = pd.read_csv(f"{self.data_dir}member_ideology.csv")
        c_votes_df = pd.read_csv(f"{self.data_dir}congressional_votes.csv")
        m_votes_df = pd.read_csv(f"{self.data_dir}member_votes.csv")
        parties_df = pd.read_csv(f"{self.data_dir}congressional_parties.csv")
        nlp_bills_df = pd.read_csv(categorized_bills_csv)

        # 2. Map Cast Codes to Binary Votes (1 = Yes, 0 = No)
        # Standard Voteview codes: 1, 2, 3 are Yea; 4, 5, 6 are Nay; 7, 8, 9 are Present/Not Voting
        logging.info("Mapping vote cast codes to binary targets...")
        m_votes_df = m_votes_df[m_votes_df['cast_code'].isin([1, 2, 3, 4, 5, 6])]  # Filter out abstains
        m_votes_df['Voted_Yes'] = m_votes_df['cast_code'].apply(lambda x: 1 if x in [1, 2, 3] else 0)

        # 3. Merge Member Votes with Member Ideology (on icpsr)
        # This gives us each vote paired with the representative's ideological score
        member_full_df = pd.merge(m_votes_df,
                                  ideology_df[['icpsr', 'bioguide_id', 'nominate_dim1', 'nominate_dim2', 'party_code']],
                                  on='icpsr', how='inner')

        # 4. Merge with Party Ideology (on party_code)
        # This allows the model to calculate how far a rep is from their party's median
        member_full_df = pd.merge(member_full_df, parties_df[['party_code', 'nominate_dim1_median']],
                                  on='party_code', how='left')

        # 5. Merge with Congressional Votes (on rollnumber)
        # This attaches the bill details to the individual votes
        vote_history_df = pd.merge(member_full_df, c_votes_df[['rollnumber', 'bill_number']],
                                   on='rollnumber', how='inner')

        # 6. Merge with NLP Categorized Bills
        # Assuming your NLP dataframe has a 'bill_number' column to join on
        logging.info("Joining ideology data with NLP bill categories...")
        final_df = pd.merge(vote_history_df, nlp_bills_df[['bill_number', 'Category_Label']],
                            on='bill_number', how='inner')

        # Calculate "Ideological Distance" from party median (great feature for tie-breakers)
        final_df['distance_from_party'] = abs(final_df['nominate_dim1'] - final_df['nominate_dim1_median'])

        logging.info(f"Final dataset ready: {final_df.shape[0]} voting records.")

        output_path = f"{self.data_dir}final_classification_dataset.csv"
        final_df.to_csv(output_path, index=False)
        logging.info(f"Exported complete classification dataset to {output_path}")

        return final_df


if __name__ == "__main__":
    merger = IdeologyMerger()
    merged_df = merger.build_classification_dataset("../data/new_data/bills_categorized.csv")