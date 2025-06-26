import streamlit as st
from collections import defaultdict
import pandas as pd
import requests

@st.cache_data(show_spinner=False)
def fetch_data(url, HEADERS):
    try:
        offset = 0
        total_data = []

        while True:
            response = requests.get(
                url, 
                headers=HEADERS,
                params= {
                    "limit": 1000,
                    "offset": offset,
                    "fields": "Full Name,Affiliation (College/Company/Organization Name),Id,Email Address",
                }
            )
            response.raise_for_status()
            data = response.json().get("list", [])
            total_data.extend(data)
            offset += 1000
            if  len(data) < 1000:
                break
        return total_data
    except Exception as e:
        print("error: ",e)
        return []

def update_users_with_gitlabinfo(gitlab_users, aidev_data, techlead_data, cohort_type):
    """
    Updates the AIDEV and TL cohort CSV file with GitLab account information.
    :param gitlab_users: List of dictionaries containing GitLab user information.
    """
    gitlab_emails = {
        user['email'].strip().lower()
        for user in gitlab_users
        if user.get('email')
    }
    aidev_data = pd.DataFrame(aidev_data)
    techlead_data = pd.DataFrame(techlead_data)

    aidev_data['has_gitlab_account'] = aidev_data['Email Address'].str.strip().str.lower().isin(gitlab_emails).map({True: 'Yes', False: 'No'})
    techlead_data['has_gitlab_account'] = techlead_data['Email Address'].str.strip().str.lower().isin(gitlab_emails).map({True: 'Yes', False: 'No'})

    # Define custom ID ranges
    aidev_ranges = {
        "cohort1": (0, 25000),
        "cohort2": (25001, 44126),
    }

    techlead_ranges = {
        "cohort1": (0, 1730),
        "cohort2": (1731, 2348),
    }

    if cohort_type not in aidev_ranges or cohort_type not in techlead_ranges:
        raise ValueError("Invalid cohort_type.")

    a_start, a_end = aidev_ranges[cohort_type]
    t_start, t_end = techlead_ranges[cohort_type]

    aidev_filtered = aidev_data[(aidev_data['Id'] >= a_start) & (aidev_data['Id'] <= a_end)]
    techlead_filtered = techlead_data[(techlead_data['Id'] >= t_start) & (techlead_data['Id'] <= t_end)]

    return aidev_filtered.to_dict(orient='records'), techlead_filtered.to_dict(orient='records')



def aggregate_collegewise_gitlab(aidev_updated, techlead_updated):
    """
    Aggregates the AIDEV cohort data by college affiliation and GitLab account status.
    :param aidev_updated: List of dictionaries containing updated AIDEV cohort data.
    :return: List of dictionaries with aggregated college-wise GitLab account information.
    """
    summary = defaultdict(lambda: {
        'total_registrations': 0,
        'no_of_accounts_created': 0,
        'no_of_accounts_needed': 0
    })

    for row in aidev_updated:
        affiliation = row['Affiliation (College/Company/Organization Name)'].strip()
        account_status = row['has_gitlab_account'].strip().lower()

        summary[affiliation]['total_registrations'] += 1
        if account_status == 'yes':
            summary[affiliation]['no_of_accounts_created'] += 1
        else:
            summary[affiliation]['no_of_accounts_needed'] += 1

    aidev_collegewise_gitlab = [
        {
            'Affiliation': affiliation,
            'total_registrations': counts['total_registrations'],
            'no_of_accounts_created': counts['no_of_accounts_created'],
            'no_of_accounts_needed': counts['no_of_accounts_needed']
        }
        for affiliation, counts in summary.items()
    ]

    summary = defaultdict(lambda: {
        'total_registrations': 0,
        'no_of_accounts_created': 0,
        'no_of_accounts_needed': 0
    })

    for row in techlead_updated:
        affiliation = row['Affiliation (College/Company/Organization Name)'].strip()
        account_status = row['has_gitlab_account'].strip().lower()

        summary[affiliation]['total_registrations'] += 1
        if account_status == 'yes':
            summary[affiliation]['no_of_accounts_created'] += 1
        else:
            summary[affiliation]['no_of_accounts_needed'] += 1

    tl_collegewise_gitlab = [
        {
            'Affiliation': affiliation,
            'total_registrations': counts['total_registrations'],
            'no_of_accounts_created': counts['no_of_accounts_created'],
            'no_of_accounts_needed': counts['no_of_accounts_needed']
        }
        for affiliation, counts in summary.items()
    ]

    return aidev_collegewise_gitlab, tl_collegewise_gitlab


def filter_no_gitlab_accounts(data_updated):
    """
    Filters the TechLead cohort data to only include users without GitLab accounts.
    """
    df = pd.DataFrame(data_updated)

    # Filter rows where has_gitlab_account is 'no'
    filtered_df = df[df['has_gitlab_account'].str.strip().str.lower() == 'no']

    # Convert back to a list of dicts
    account_creation = filtered_df.to_dict(orient='records')

    return account_creation

