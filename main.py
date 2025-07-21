# main.py

import os
import pandas as pd
import numpy as np
import random
from collections import defaultdict
import streamlit as st
import plotly.express as px

# Ensure outputs directory exists
os.makedirs("outputs", exist_ok=True)

# Load data
df = pd.read_csv("player_data_sample.csv")
TOTAL_TEAMS = 20000
TEAM_SIZE = 11
roles = ['Batsman', 'Bowler', 'WK', 'Allrounder']
role_players = {role: df[df['role'] == role] for role in roles}

# Team Generation
generated_teams = set()
teams_list = []
team_id = 0
attempts = 0
max_attempts = TOTAL_TEAMS * 3

while len(generated_teams) < TOTAL_TEAMS and attempts < max_attempts:
    team = set()
    for role in roles:
        population = role_players[role]['player_code'].reset_index(drop=True).tolist()
        weights = role_players[role]['perc_selection'].reset_index(drop=True).tolist()
        sampled = random.choices(population, weights=weights)[0]
        team.add(sampled)
    while len(team) < TEAM_SIZE:
        pid = random.choices(df['player_code'], weights=df['perc_selection'])[0]
        team.add(pid)
    team_tuple = tuple(sorted(team))
    if team_tuple not in generated_teams:
        generated_teams.add(team_tuple)
        for pid in team_tuple:
            pdata = df[df['player_code'] == pid].iloc[0]
            teams_list.append({
                'match_code': pdata['match_code'],
                'player_code': pdata['player_code'],
                'player_name': pdata['player_name'],
                'role': pdata['role'],
                'team': pdata['team'],
                'perc_selection': pdata['perc_selection'],
                'team_id': team_id
            })
        team_id += 1
    attempts += 1

team_df = pd.DataFrame(teams_list)
team_df.to_csv("outputs/team_df.csv", index=False)

# Evaluation Function
def evaluate_team_accuracy(team_df):
    print("\U0001F50D Evaluating Fantasy Team Accuracy...\n")

    print(f"\U0001F4D0 team_df shape: {team_df.shape}")
    total_teams = team_df['team_id'].nunique()
    total_players = team_df['player_code'].nunique()
    print(f"\U0001F465 Total unique teams: {total_teams}")
    print(f"✪ Total unique players: {total_players}")

    role_per_team = team_df.groupby('team_id')['role'].nunique()
    missing_role_teams = role_per_team[role_per_team < 4].count()
    print(f"⚠️ Teams missing at least one role: {missing_role_teams} / {total_teams}\n")

    player_ref = team_df.drop_duplicates(subset='player_code')[
        ['match_code', 'player_code', 'player_name', 'role', 'team', 'perc_selection']
    ].copy()

    team_counts = team_df.groupby('player_code')['team_id'].nunique().reset_index(name='actual_team_count')
    merged = pd.merge(player_ref, team_counts, on='player_code', how='left')
    merged['actual_team_count'] = merged['actual_team_count'].fillna(0).astype(int)

    merged['expected_team_count'] = (merged['perc_selection'] * total_teams).round(0).astype(int)
    merged['actual_perc_selection'] = merged['actual_team_count'] / total_teams

    merged['expected_std'] = np.sqrt(merged['perc_selection'] * (1 - merged['perc_selection']) * total_teams)
    merged['z_score'] = (merged['actual_team_count'] - merged['expected_team_count']) / merged['expected_std']

    merged['perc_error'] = (
        (merged['actual_perc_selection'] - merged['perc_selection']) / merged['perc_selection']
    ).round(4)

    merged['perc_selection'] = (merged['perc_selection'] * 100).round(2)
    merged['actual_perc_selection'] = (merged['actual_perc_selection'] * 100).round(2)
    merged['perc_error'] = (merged['perc_error'] * 100).round(2)

    accuracy_df = merged[[
        'match_code', 'player_code', 'player_name', 'role', 'team',
        'perc_selection', 'expected_team_count', 'actual_team_count',
        'actual_perc_selection', 'perc_error', 'z_score'
    ]].sort_values('player_code')

    within_5 = accuracy_df[accuracy_df['perc_error'].abs() <= 5]
    outside_5 = accuracy_df[accuracy_df['perc_error'].abs() > 5]

    print("\U0001F4CA Accuracy KPIs:")
    print(f"✅ Players within ±5% relative error: {within_5.shape[0]} / {accuracy_df.shape[0]}")
    print(f"❌ Players outside ±5% error: {outside_5.shape[0]}")
    print(f"\U0001F4C9 Minimum error: {accuracy_df['perc_error'].min():.2f}%")
    print(f"\U0001F4C8 Maximum error: {accuracy_df['perc_error'].max():.2f}%\n")

    if not outside_5.empty:
        print("\U0001F6A8 Players with >5% relative error:\n")
        print(outside_5[['player_code', 'player_name', 'perc_selection',
                         'actual_perc_selection', 'perc_error']].to_string(index=False))

    accuracy_df.to_csv("outputs/accuracy_summary.csv", index=False)
    print("\n✅ Accuracy summary saved as 'outputs/accuracy_summary.csv'")

    return accuracy_df

# Run evaluation and capture DataFrame
accuracy_df = evaluate_team_accuracy(team_df)

# Streamlit Dashboard
st.title("Fantasy Team Simulation Dashboard")
st.dataframe(accuracy_df)
accuracy_df['abs_z_score'] = accuracy_df['z_score'].abs()
fig = px.bar(accuracy_df, x='player_name', y='perc_error', color='z_score',
             title="Selection Error vs Confidence", color_continuous_scale='RdBu')
st.plotly_chart(fig)
fig2 = px.scatter(accuracy_df, x='perc_selection', y='actual_perc_selection', text='player_name', 
                  size='abs_z_score', color='role', size_max=40, 
                  title="Expected vs Actual Selection (by Abs Z-Score)")
st.plotly_chart(fig2)
