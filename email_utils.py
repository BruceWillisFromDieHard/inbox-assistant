import os
import logging
from datetime import datetime
import httpx
from openai import OpenAI
from auth import get_access_token

# Configure logging at INFO level
logging.basicConfig(level=logging.INFO)

# Base URL for Microsoft Graph
GRAPH_URL = "https://graph.microsoft.com/v1.0"

def _parse_iso(dt_str: str) -> datetime | None:
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None

def fetch_emails_since(from_time_iso: str) -> list[dict]:
    cutoff = _parse_iso(from_time_iso)
    if cutoff is None:
        raise ValueError(f"Invalid from_time: {from_time_iso}")

    token   = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    url     = f"{GRAPH_URL}/users/{os.getenv('USER_ID')}/mailFolders/Inbox/messages"
    params  = {
        "$orderby": "receivedDateTime desc",
        "$top": 50,
        "$select": "subject,receivedDateTime,from,bodyPreview"
    }

    logging.info("📬 Fetching inbox batch without filter...")
    resp = httpx.get(url, headers=headers, params=params)
    resp.raise_for_status()
    items = resp.json().get("value", [])

    filtered = []
    for item in items:
        received = _parse_iso(item.get("receivedDateTime", ""))
        if received and received >= cutoff:
            filtered.append(item)
        else:
            break

    logging.info("✅ %d emails after local filter", len(filtered))
    return filtered

def analyze_emails(emails: list[dict]) -> str:
    if not emails:
        return "No new emails since that time."

    prompts = []
    for e in emails:
        sender  = e.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
        subject = e.get("subject", "(No subject)")
        preview = e.get("bodyPreview", "").replace("\n", " ").strip()
        prompts.append(f"From {sender}: {subject} — {preview}")

    logging.info("💬 Summarizing %d emails via OpenAI...", len(prompts))
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a concise assistant. Summarize and prioritize these emails."},
            {"role": "user",   "content": "\n\n".join(prompts)}
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content