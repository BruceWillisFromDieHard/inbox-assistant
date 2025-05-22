import os
import logging
from datetime import datetime
import httpx
import openai
from dotenv import load_dotenv
from auth import get_access_token

# Load environment vars from .env (project root)
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Base URL for Microsoft Graph
GRAPH_URL = "https://graph.microsoft.com/v1.0"

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
        raise ValueError(f"Invalid from_time: {from_time_iso!r}")

    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GRAPH_URL}/users/{os.getenv('USER_ID')}/mailFolders/Inbox/messages"
    params = {
        "$orderby": "receivedDateTime desc",
        "$top": 50,
        "$select": "subject,receivedDateTime,from,bodyPreview",
    }

    logging.info("📬 Fetching inbox batch without Graph filter...")
    r = httpx.get(url, headers=headers, params=params)
    r.raise_for_status()
    items = r.json().get("value", [])

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

    summaries = []
    for e in emails:
        sender = e.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
        subject = e.get("subject", "(No subject)")
        preview = e.get("bodyPreview", "").replace("\n", " ").strip()
        summaries.append(f"From {sender}: {subject} — {preview}")

    # Choose model (override via env var if needed)
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    openai.api_key = os.getenv("OPENAI_API_KEY")
    logging.info("💬 Summarizing %d emails via OpenAI model=%s...", len(summaries), model)

    try:
        resp = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise assistant. Summarize and prioritize these emails."},
                {"role": "user",   "content": "\n\n".join(summaries)},
            ],
            temperature=0.7,
        )
    except openai.error.InvalidRequestError as ice:
        # Usually model-not-found or access-denied
        logging.error("❌ OpenAI request failed: %s", ice)
        raise RuntimeError(f"OpenAI error: {ice}")

    return resp.choices[0].message.content