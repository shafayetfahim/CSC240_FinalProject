# import pandas as pd

# def engineer_political_features(history_csv, reps_csv):
#     history = pd.read_csv(history_csv)
#     reps = pd.read_csv(reps_csv)
#     df = pd.merge(history, reps[['UID', 'party', 'state']], on='UID')

#     # 1. Calculate Partisan Benchmarks
#     party_majority = df.groupby(['party', 'Category_Label'])['Voted_Yes'].transform(lambda x: x.mode()[0])
#     df['is_partisan_vote'] = (df['Voted_Yes'] == party_majority).astype(int)

#     # 2. Calculate Delegate Benchmarks (State Proxy)
#     state_majority = df.groupby(['state', 'Category_Label'])['Voted_Yes'].transform(lambda x: x.mode()[0])
#     df['is_delegate_vote'] = (df['Voted_Yes'] == state_majority).astype(int)

#     # 3. Trustee Score (Outlier behavior)
#     df['is_trustee_vote'] = ((df['Voted_Yes'] != party_majority) & (df['Voted_Yes'] != state_majority)).astype(int)

#     return df

import pandas as pd

def engineer_political_features(train_df, test_df):
    """
    Implements Partisan and Delegate models by calculating 
    benchmarks on TRAIN and applying them to TEST.
    """
    # 1. Calculate Expected Vote (Mode) per Party/Category on TRAIN only
    # This prevents the model from 'seeing' the test set results in advance
    party_map = train_df.groupby(['party', 'Category_Label'])['Voted_Yes'].agg(
        lambda x: x.mode()[0] if not x.empty else 0
    ).to_dict()

    state_map = train_df.groupby(['state', 'Category_Label'])['Voted_Yes'].agg(
        lambda x: x.mode()[0] if not x.empty else 0
    ).to_dict()

    # 2. Map these 'Social Expectations' to both DataFrames
    for df in [train_df, test_df]:
        df['party_expected'] = df.apply(lambda x: party_map.get((x.party, x.Category_Label), 0), axis=1)
        df['state_expected'] = df.apply(lambda x: state_map.get((x.state, x.Category_Label), 0), axis=1)
        
        # Trustee Indicator: Defying both Party and State norms
        df['is_trustee_action'] = ((df['Voted_Yes'] != df['party_expected']) & 
                                   (df['Voted_Yes'] != df['state_expected'])).astype(int)

    return train_df, test_df