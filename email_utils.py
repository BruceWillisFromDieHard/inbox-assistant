import os
import httpx
import logging
from auth import get_access_token
from datetime import datetime
import openai

GRAPH_URL = "https://graph.microsoft.com/v1.0"

openai.api_key = os.getenv("OPENAI_API_KEY")
logging.basicConfig(level=logging.INFO)

def fetch_emails_since(from_time_iso):
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }

    url = f"{GRAPH_URL}/users/{os.getenv('USER_ID')}/messages"
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
    summaries = []
    for e in emails:
        try:
            sender = e.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
            subject = e.get("subject", "(No subject)")
            preview = e.get("bodyPreview", "").strip()
            summaries.append(f"From {sender}: {subject} — {preview}")
        except Exception as ex:
            logging.warning("⚠️ Failed to parse one email: %s", ex)

    if not summaries:
        return "No relevant emails found."

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Summarize and prioritize these emails. Focus on what the user should know or act on."},
            {"role": "user", "content": "\n\n".join(summaries)}
        ]
    )

    return response["choices"][0]["message"]["content"]