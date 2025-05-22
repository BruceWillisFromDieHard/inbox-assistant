import os
import httpx
import logging
import openai
from auth import get_access_token

GRAPH_URL = "https://graph.microsoft.com/v1.0"

def fetch_emails_since(from_time_iso):
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }

    # ✅ Use the /mailFolders/Inbox/messages endpoint
    url = f"{GRAPH_URL}/users/{os.getenv('USER_ID')}/mailFolders/Inbox/messages"
    params = {
        "$orderby": "receivedDateTime desc",
        "$top": 20,
        "$filter": f"receivedDateTime ge {from_time_iso}",
        "$select": "subject,receivedDateTime,from,bodyPreview"
    }

    logging.info("📬 Fetching emails since: %s", from_time_iso)
    r = httpx.get(url, headers=headers, params=params)
    r.raise_for_status()

    emails = r.json().get("value", [])
    logging.info("✅ %d emails fetched", len(emails))
    return emails


def analyze_emails(emails):
    summaries = [
        f"From {e['from']['emailAddress']['name']}: {e['subject']}\n{e['bodyPreview']}"
        for e in emails
    ]

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Summarize and prioritize these emails. Format as a briefing."},
            {"role": "user", "content": "\n\n".join(summaries)}
        ]
    )

    return response["choices"][0]["message"]["content"]