import httpx
import os
from datetime import datetime, timedelta
from auth import get_access_token
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")

GRAPH_URL = "https://graph.microsoft.com/v1.0"

def fetch_emails_since(from_time_iso):
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{GRAPH_URL}/users/{os.getenv('USER_ID')}/mailFolders/Inbox/messages"
    params = {
        "$orderby": "receivedDateTime desc",
        "$top": 20,
        "$filter": f"receivedDateTime ge {from_time_iso}"
    }

    r = httpx.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json().get("value", [])

def analyze_emails(emails):
    summaries = []
    for email in emails:
        summaries.append(f"From {email['sender']['emailAddress']['name']}: {email['subject']}\n{email['body']['content'][:500]}")
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{
            "role": "system",
            "content": "You're a sharp executive assistant. Summarize and prioritize these emails. Focus on urgency, actions, and meaning — not just topics."
        }, {
            "role": "user",
            "content": "\n\n".join(summaries)
        }]
    )
    return response["choices"][0]["message"]["content"]