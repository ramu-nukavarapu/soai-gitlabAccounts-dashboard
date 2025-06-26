import asyncio
import aiohttp
import streamlit as st

GITLAB_URL = "https://code.swecha.org"
TOKEN = st.secrets["GITLAB_TOKEN"]
HEADERS = {"PRIVATE-TOKEN": TOKEN}

async def fetch_page(session, page):
    url = f"{GITLAB_URL}/api/v4/users"
    async with session.get(url, headers=HEADERS, params={"per_page": 100, "page": page}) as response:
        try:
            return await response.json()
        except Exception as e:
            text = await response.text()
            raise RuntimeError(f"Failed to decode JSON on page {page}: {e} — Response: {text}")

async def fetch_gitlab_users_concurrent(total_pages):
    users = []
    async with aiohttp.ClientSession() as session:
        # First, determine how many pages there are by checking the first page headers
        first_page = await fetch_page(session, 1)
        users.extend(first_page)

        # GitLab includes pagination headers — for simplicity, guess number of pages
        # You can extract 'X-Total-Pages' header from the initial response in real use
        # Here we estimate conservatively if not known
        # total_pages = 100  # Adjust or dynamically calculate if possible

        tasks = [fetch_page(session, page) for page in range(1, total_pages + 1)]
        results = await asyncio.gather(*tasks)

        for result in results:
            if result:
                users.extend(result)

    return users

# To run the async function
@st.cache_data(show_spinner=False)
def get_all_users():
    return asyncio.run(fetch_gitlab_users_concurrent(500))
