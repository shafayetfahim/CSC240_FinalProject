import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CongressMiner:
    def __init__(self, data_dir="../data/new_data/"):
        self.data_dir = data_dir

    def clean_congressional_votes(self):
        """
        Cleans congressional_votes.csv and maps text fields to 'Title' and 'Summary'
        so it is compatible with the legacy categorize.py NLP pipeline.
        """
        input_file = f"{self.data_dir}/unclean_data/congressional_votes.csv"
        output_file = f"{self.data_dir}congressional_votes_cleaned.csv"
        logging.info(f"Cleaning {input_file}...")

        try:
            df = pd.read_csv(input_file)

            # Map 'vote_question' to 'Title' for the NLP categorizer
            df['Title'] = df['vote_question'].fillna('Unknown Vote')

            # Combine descriptions to act as the comprehensive 'Summary'
            df['Summary'] = df['vote_desc'].fillna('') + " " + df['dtl_desc'].fillna('')

            # Handle edge cases where both descriptions are empty
            df['Summary'] = df['Summary'].replace(r'^\s*$', pd.NA, regex=True).fillna(df['Title'])

            df.to_csv(output_file, index=False)
            logging.info(f"Saved cleaned congressional votes to {output_file}")
            return output_file
        except Exception as e:
            logging.error(f"Failed to clean congressional votes: {e}")

    def clean_member_votes(self):
        """
        Cleans member_votes.csv by removing abstains/absences and converting
        the standard VoteView cast codes into a binary 'Voted_Yes' target.
        """
        input_file = f"{self.data_dir}/unclean_data/member_votes.csv"
        output_file = f"{self.data_dir}member_votes_cleaned.csv"
        logging.info(f"Cleaning {input_file}...")

        try:
            df = pd.read_csv(input_file)

            # Filter out non-votes (7, 8, 9 are usually present, absent, or not voting)
            # Keep only 1,2,3 (Yea variants) and 4,5,6 (Nay variants)
            df = df[df['cast_code'].isin([1, 2, 3, 4, 5, 6])].copy()

            # Create the binary classification target
            df['Voted_Yes'] = df['cast_code'].apply(lambda x: 1 if x in [1, 2, 3] else 0)

            df.to_csv(output_file, index=False)
            logging.info(f"Saved cleaned member votes to {output_file}")
            return output_file
        except Exception as e:
            logging.error(f"Failed to clean member votes: {e}")

    def clean_member_ideology(self):
        """
        Cleans member_ideology.csv by ensuring critical DW-NOMINATE features
        are present, as they are required for the BOAT classifier.
        """
        input_file = f"{self.data_dir}/unclean_data/member_ideology.csv"
        output_file = f"{self.data_dir}member_ideology_cleaned.csv"
        logging.info(f"Cleaning {input_file}...")

        try:
            df = pd.read_csv(input_file)

            # Drop rows where the representative has no ideology score
            # (sometimes happens with brand-new members or errors in the data)
            df = df.dropna(subset=['nominate_dim1', 'nominate_dim2', 'party_code'])

            df.to_csv(output_file, index=False)
            logging.info(f"Saved cleaned member ideology to {output_file}")
            return output_file
        except Exception as e:
            logging.error(f"Failed to clean member ideology: {e}")

    def clean_congressional_parties(self):
        """
        Cleans congressional_parties.csv by dropping empty rows and ensuring valid median scores.
        """
        input_file = f"{self.data_dir}/unclean_data/congressional_parties.csv"
        output_file = f"{self.data_dir}congressional_parties_cleaned.csv"
        logging.info(f"Cleaning {input_file}...")

        try:
            df = pd.read_csv(input_file)

            # Ensure the median scores exist so we can calculate "distance_from_party" later
            df = df.dropna(subset=['nominate_dim1_median', 'nominate_dim2_median'])

            df.to_csv(output_file, index=False)
            logging.info(f"Saved cleaned congressional parties to {output_file}")
            return output_file
        except Exception as e:
            logging.error(f"Failed to clean congressional parties: {e}")

    def run_all_cleaning(self):
        """Executes all cleaning methods and returns a dictionary of the new file paths."""
        logging.info("--- STARTING DATA INGESTION & CLEANING ---")
        return {
            "votes": self.clean_congressional_votes(),
            "member_votes": self.clean_member_votes(),
            "ideology": self.clean_member_ideology(),
            "parties": self.clean_congressional_parties()
        }


if __name__ == "__main__":
    miner = CongressMiner()
    miner.run_all_cleaning()