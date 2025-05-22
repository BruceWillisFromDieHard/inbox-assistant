import os
import httpx
import logging
import openai
from auth import get_access_token
from datetime import datetime, timezone

GRAPH_URL = "https://graph.microsoft.com/v1.0"
logging.basicConfig(level=logging.INFO)

def _parse_iso(dt_str: str) -> datetime | None:
    """Parse an ISO8601 string, handling trailing Z."""
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None

def fetch_emails_since(from_time_iso: str):
    # 1) Parse cutoff
    cutoff = _parse_iso(from_time_iso)
    if cutoff is None:
        raise ValueError(f"Invalid from_time: {from_time_iso}")

    # 2) Call Graph without $filter
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GRAPH_URL}/users/{os.getenv('USER_ID')}/mailFolders/Inbox/messages"
    params = {
        "$orderby": "receivedDateTime desc",
        "$top": 50,  # grab a batch and filter locally
        "$select": "subject,receivedDateTime,from,bodyPreview"
    }

    logging.info("📬 Fetching inbox batch (no filter)...")
    r = httpx.get(url, headers=headers, params=params)
    r.raise_for_status()
    items = r.json().get("value", [])

    # 3) Filter in Python
    filtered = []
    for item in items:
        dt = _parse_iso(item.get("receivedDateTime", ""))
        if dt and dt >= cutoff:
            filtered.append(item)
        else:
            break  # messages are ordered descending, so once we drop below cutoff we can stop

    logging.info("✅ %d messages after local filter", len(filtered))
    return filtered

def analyze_emails(emails):
    if not emails:
        return "No new emails since that time."

    summaries = []
    for e in emails:
        sender = e.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
        subj   = e.get("subject", "(No subject)")
        body   = e.get("bodyPreview", "").replace("\n", " ").strip()
        summaries.append(f"From {sender}: {subj} — {body}")

    logging.info("💬 Summarizing %d messages via OpenAI...", len(summaries))
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are a concise assistant. Summarize and prioritize these emails."
            },
            {
                "role": "user",
                "content": "\n\n".join(summaries)
            }
        ],
        temperature=0.7,
    )

    return response.choices[0].message.content