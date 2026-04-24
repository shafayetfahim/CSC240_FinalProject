import pandas as pd

def engineer_political_features(history_csv, reps_csv):
    history = pd.read_csv(history_csv)
    reps = pd.read_csv(reps_csv)
    df = pd.merge(history, reps[['UID', 'party', 'state']], on='UID')

    # 1. Calculate Partisan Benchmarks
    party_majority = df.groupby(['party', 'Category_Label'])['Voted_Yes'].transform(lambda x: x.mode()[0])
    df['is_partisan_vote'] = (df['Voted_Yes'] == party_majority).astype(int)

    # 2. Calculate Delegate Benchmarks (State Proxy)
    state_majority = df.groupby(['state', 'Category_Label'])['Voted_Yes'].transform(lambda x: x.mode()[0])
    df['is_delegate_vote'] = (df['Voted_Yes'] == state_majority).astype(int)

    # 3. Trustee Score (Outlier behavior)
    df['is_trustee_vote'] = ((df['Voted_Yes'] != party_majority) & (df['Voted_Yes'] != state_majority)).astype(int)

    return df