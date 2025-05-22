import os
import logging
from datetime import datetime
import httpx
from openai import OpenAI, OpenAIError
from auth import get_access_token

# Configure logging at INFO level
logging.basicConfig(level=logging.INFO)

# Base URL for Microsoft Graph
GRAPH_URL = "https://graph.microsoft.com/v1.0"

# Initialize the OpenAI v1 client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _parse_iso(dt_str: str) -> datetime | None:
    """
    Parse an ISO8601 string into a datetime.
    Accepts strings ending with 'Z' or with an offset.
    Returns None if parsing fails.
    """
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def fetch_emails_since(from_time_iso: str) -> list[dict]:
    """
    Fetch the latest 50 emails from the user's Inbox, then filter in Python
    for those received at or after the given ISO timestamp.
    """
    cutoff = _parse_iso(from_time_iso)
    if cutoff is None:
        raise ValueError(f"Invalid from_time: {from_time_iso}")

    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GRAPH_URL}/users/{os.getenv('USER_ID')}/mailFolders/Inbox/messages"
    params = {
        "$orderby": "receivedDateTime desc",
        "$top": 50,
        "$select": "subject,receivedDateTime,from,bodyPreview"
    }

    logging.info("📬 Fetching inbox batch without filter…")
    response = httpx.get(url, headers=headers, params=params)
    response.raise_for_status()
    items = response.json().get("value", [])

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
    """
    Summarize and prioritize a list of email dicts using OpenAI.
    """
    if not emails:
        return "No new emails since that time."

    system_msg = {
        "role": "system",
        "content": "You are a concise assistant. Summarize and prioritize these emails."
    }
    user_items = []
    for e in emails:
        sender  = e.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
        subject = e.get("subject", "(No subject)")
        preview = e.get("bodyPreview", "").replace("\n", " ").strip()
        user_items.append(f"From {sender}: {subject} — {preview}")

    user_msg = {
        "role": "user",
        "content": "\n\n".join(user_items)
    }

    logging.info("💬 Asking OpenAI to summarize %d emails…", len(emails))
    try:
        model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        resp = openai_client.chat.completions.create(
            model=model,
            messages=[system_msg, user_msg],
            temperature=0.7
        )
    except OpenAIError as e:
        logging.error("⚠️ OpenAI error: %s", e)
        raise RuntimeError(f"OpenAI request failed: {e}")

    return resp.choices[0].message.content
