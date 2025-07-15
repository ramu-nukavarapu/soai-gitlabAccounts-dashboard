import streamlit as st
import pandas as pd
import altair as alt
from gitlab_users import get_all_users
from users_data import (
    fetch_data,
    update_users_with_gitlabinfo,
    aggregate_collegewise_gitlab,
    filter_no_gitlab_accounts
)
import streamlit_authenticator as stauth
import yaml

st.set_page_config(page_title="GitLab Account Dashboard", layout="centered")

# Load signing key securely
signing_key = st.secrets["COOKIE_SIGNING_KEY"]
API_TOKEN = st.secrets["API_TOKEN"]
API_URL = st.secrets["API_URL"]
LEAD_URL = st.secrets["LEAD_URL"]

HEADERS = {
    "accept": "application/json",
    "xc-token": API_TOKEN
}

# Define user credentials (or load from a YAML file)
config = yaml.safe_load(st.secrets["CONFIG_YAML"])

authenticator = stauth.Authenticate(
    config['credentials'],
    "gitlab_cookie", 
    signing_key, 
    cookie_expiry_days=1
)

authenticator.login(location='main')

if st.session_state.get("authentication_status"):
    st.sidebar.success(f"Welcome {st.session_state['name']} 👋")
    authenticator.logout(location='sidebar')
    # --- Streamlit Setup ---
    st.title("🔍 GitLab Account Dashboard for AIDEV & TechLeads")

    # --- Session Defaults ---
    if 'gitlab_users' not in st.session_state:
        st.session_state.gitlab_users = None
    if 'aidev_data' not in st.session_state:
        st.session_state.aidev_data = None
    if 'techlead_data' not in st.session_state:
        st.session_state.techlead_data = None
    if 'aidev_updated' not in st.session_state:
        st.session_state.aidev_updated = None
    if 'techlead_updated' not in st.session_state:
        st.session_state.techlead_updated = None
    if 'aidev_df' not in st.session_state:
        st.session_state.aidev_df = None
    if 'techlead_df' not in st.session_state:
        st.session_state.techlead_df = None
    if 'selected_group' not in st.session_state:
        st.session_state.selected_group = "aidev"
    if "cohort_type" not in st.session_state: 
        st.session_state.cohort_type = "cohort1"

    @st.cache_data
    def load_all_data():
        """Fetches both datasets and returns them as a tuple."""
        ai_data = fetch_data(API_URL, HEADERS)
        techlead_data = fetch_data(LEAD_URL, HEADERS)
        return ai_data, techlead_data

    # Load the data once using the cached function
    if not st.session_state.aidev_data or not st.session_state.techlead_data:
        st.session_state.aidev_data, st.session_state.techlead_data = load_all_data()

    st.subheader("Select Cohort")
    selected_cohort = st.selectbox("Choose a cohort:", ["cohort1", "cohort2"], key="cohort_selector")
    st.session_state.cohort_type = selected_cohort
    st.subheader(f"Selected Cohort: {st.session_state.cohort_type.upper()}")

    # --- Fetch Data Button ---
    if st.button("Fetch GitLab Users and Process") or not st.session_state.gitlab_users:
        with st.spinner("Fetching GitLab users from GitLab API..."):
            try:
                st.session_state.gitlab_users = get_all_users()
            except Exception as e:
                st.error(f"Error fetching GitLab users: {e}")
                st.stop()

    st.success(f"Fetched {len(st.session_state.gitlab_users)} GitLab users.")

    # Process Users
    aidev_updated, techlead_updated = update_users_with_gitlabinfo(st.session_state.gitlab_users, st.session_state.aidev_data, st.session_state.techlead_data, st.session_state.cohort_type)
    st.session_state.aidev_updated = aidev_updated
    st.session_state.techlead_updated = techlead_updated

    # Aggregated Data
    aidev_summary, techlead_summary = aggregate_collegewise_gitlab(aidev_updated, techlead_updated)
    st.session_state.aidev_df = pd.DataFrame(aidev_summary)
    st.session_state.techlead_df = pd.DataFrame(techlead_summary)

    # --- Only continue if data is fetched ---
    if st.session_state.gitlab_users is not None:

        st.subheader("Select User Group")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🧠 AI Developers"):
                st.session_state.selected_group = 'aidev'
        with col2:
            if st.button("🛠️ Tech Leads"):
                st.session_state.selected_group = 'techlead'

        if st.session_state.selected_group is None:
            st.warning("Please select a group to continue.")
            st.stop()

        selected_df = (
            st.session_state.aidev_df if st.session_state.selected_group == 'aidev'
            else st.session_state.techlead_df
        )
        group_label = "AI Developers" if st.session_state.selected_group == 'aidev' else "Tech Leads"

        if selected_df is None or selected_df.empty:
            st.warning("No data found for selected group.")
            st.stop()

        # Clean & preprocess
        selected_df.fillna('Unknown', inplace=True)

        for col in ['no_of_accounts_created', 'no_of_accounts_needed']:
            selected_df[col] = pd.to_numeric(selected_df[col], errors='coerce').fillna(0).astype(int)

        selected_df = selected_df.sort_values(by='total_registrations', ascending=False)

        # Sidebar slider
        top_n = st.sidebar.slider("Show Top N Affiliations", min_value=1, max_value=10, value=5)
        top_df = selected_df.head(top_n)

        # Melt for bar chart
        chart_data = pd.melt(
            top_df,
            id_vars=['Affiliation'],
            value_vars=['no_of_accounts_created', 'no_of_accounts_needed'],
            var_name='Status',
            value_name='Count'
        )

        chart_data['Status Label'] = chart_data['Status'].map({
            'no_of_accounts_created': 'Created',
            'no_of_accounts_needed': 'Needs'
        })

        # Altair grouped bar chart
        grouped_bar = alt.Chart(chart_data).mark_bar().encode(
            x=alt.X('Affiliation:N', title='Affiliation', axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('Count:Q'),
            color=alt.Color('Status Label:N', scale=alt.Scale(domain=['Created', 'Needs'], range=['#4CAF50', '#F44336'])),
            tooltip=['Affiliation', 'Status Label', 'Count'],
            xOffset='Status Label:N'
        ).properties(
            width=900,
            height=400,
            title=f"Top {top_n} Affiliations - {group_label}"
        )

        st.altair_chart(grouped_bar, use_container_width=True)

        # --- Search Interface ---
        st.subheader("🔍 Search for a College or Organization")
        search_term = st.text_input("Type to search affiliation:", "")
        filtered_options = selected_df[selected_df['Affiliation'].str.contains(search_term, case=False, na=False)]['Affiliation'].unique()

        if len(filtered_options) > 0:
            selected_affiliation = st.selectbox("Matching affiliations:", options=filtered_options)
            selected_data = selected_df[selected_df['Affiliation'] == selected_affiliation].iloc[0]

            st.markdown(f"### 📊 Account Status for: {selected_affiliation}")
            detail_df = pd.DataFrame({
                'Status': ['Created', 'Needs'],
                'Count': [selected_data['no_of_accounts_created'], selected_data['no_of_accounts_needed']],
                'Color': ['#4CAF50', '#F44336']
            })

            detail_chart = alt.Chart(detail_df).mark_bar().encode(
                x=alt.X('Status:N'),
                y=alt.Y('Count:Q'),
                color=alt.Color('Color:N', scale=None),
                tooltip=['Status', 'Count']
            ).properties(width=300, height=300)

            st.altair_chart(detail_chart)
        elif search_term:
            st.warning("No matching affiliations found.")

        # --- Downloads ---
        st.subheader("Interns who need to create account in gitlab")
        indices = ['Full Name','Affiliation (College/Company/Organization Name)']
        if st.session_state.selected_group == 'aidev':
            aidev_missing = filter_no_gitlab_accounts(st.session_state.aidev_updated)
            st.metric("AI Developers who create accounts in gitlab",len(st.session_state.aidev_updated)-len(aidev_missing))
            st.metric("AI Developers need to create accounts in gitlab",len(aidev_missing))
            
            data = pd.DataFrame(aidev_missing)
            data = data[indices]
            st.dataframe(data, use_container_width=True)

            selected_colleges = st.multiselect("Filter by College(s)", options=data['Affiliation (College/Company/Organization Name)'].unique(), default=[])
            if selected_colleges:
                filtered_data = data[data['Affiliation (College/Company/Organization Name)'].isin(selected_colleges)]
                if filtered_data.empty:
                    st.warning("No data available for the selected colleges.")
                else:
                    st.dataframe(filtered_data, use_container_width=True)   
        else:
            techlead_missing = filter_no_gitlab_accounts(st.session_state.techlead_updated)
            st.metric("Tech Leads need to create accounts in gitlab",len(st.session_state.techlead_updated)-len(techlead_missing))
            st.metric("Tech Leads need to create accounts in gitlab",len(techlead_missing))
            data = pd.DataFrame(techlead_missing)
            data = data[indices]
            st.dataframe(data, use_container_width=True)

            selected_colleges = st.multiselect("Filter by College(s)", options=data['Affiliation (College/Company/Organization Name)'].unique(), default=[])

            if selected_colleges:
                filtered_data = data[data['Affiliation (College/Company/Organization Name)'].isin(selected_colleges)]
                if filtered_data.empty:
                    st.warning("No data available for the selected colleges.")
                else:
                    st.dataframe(filtered_data, use_container_width=True)
    else:
        st.info("Click the button above to fetch GitLab data.")
elif st.session_state.get("authentication_status") is False:
    st.error("Username/password incorrect")
else:
    st.warning("Please enter your credentials")