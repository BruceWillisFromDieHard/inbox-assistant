import httpx
import os
import openai
from auth import get_access_token

openai.api_key = os.getenv("OPENAI_API_KEY")
GRAPH_URL = "https://graph.microsoft.com/v1.0"

def fetch_emails_since(from_time_iso):
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
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
    if not emails:
        return "No recent emails found."

    summaries = []
    for e in emails:
        try:
            name = e.get("sender", {}).get("emailAddress", {}).get("name", "Unknown Sender")
            subject = e.get("subject", "[No Subject]")
            body = e.get("body", {}).get("content", "")
            summaries.append(f"From {name}: {subject}\n{body[:300]}")
        except Exception as ex:
            summaries.append(f"[Error parsing email: {ex}]")

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Summarize and prioritize these emails. Focus on urgency, decisions, tone, and meaning — not just subject lines."},
            {"role": "user", "content": "\n\n".join(summaries)}
        ]
    )

    return response["choices"][0]["message"]["content"]