# email_utils.py
import os
import logging
from datetime import datetime, timezone
import httpx
from openai import OpenAI, OpenAIError
from auth import get_access_token

# Configure logging
logging.basicConfig(level=logging.INFO)

# Graph base
GRAPH_URL = "https://graph.microsoft.com/v1.0"

# OpenAI v1 client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _parse_iso(dt_str: str) -> datetime | None:
    try:
        # normalize trailing Z
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None

def fetch_emails_since(
    from_time_iso: str,
    max_messages: int = 200
) -> list[dict]:
    """
    Page through Inbox/messages in batches of 50 until you've
    collected up to max_messages *new* items since from_time_iso.
    """
    cutoff = _parse_iso(from_time_iso)
    if cutoff is None:
        raise ValueError(f"Invalid from_time: {from_time_iso}")
    # ensure cutoff is aware in UTC
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)

    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    # initial endpoint
    url = f"{GRAPH_URL}/users/{os.getenv('USER_ID')}/mailFolders/Inbox/messages"
    params = {
        "$orderby": "receivedDateTime desc",
        "$top": 50,
        "$select": "subject,receivedDateTime,from,bodyPreview"
    }

    collected = []
    while url and len(collected) < max_messages:
        resp = httpx.get(url, headers=headers, params=params if params else {})
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("value", []):
            r = _parse_iso(item["receivedDateTime"])
            if not r:
                continue
            if r.tzinfo is None:
                r = r.replace(tzinfo=timezone.utc)
            if r >= cutoff:
                collected.append(item)
                if len(collected) >= max_messages:
                    break
            else:
                # once we hit older, stop entirely
                url = None
                break

        url = data.get("@odata.nextLink")
        params = None  # nextLink already has query

    logging.info("📬 Fetched %d emails (max %d)", len(collected), max_messages)
    return collected

def analyze_emails(emails: list[dict]) -> str:
    """
    Summarize up to ~50 emails in one shot via OpenAI.
    """
    if not emails:
        return "No new emails since that time."

    system = {
        "role": "system",
        "content": "You are a concise assistant. Summarize and prioritize these emails."
    }
    user_lines = []
    for e in emails:
        sender  = e.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
        subj    = e.get("subject", "(No subject)")
        preview = e.get("bodyPreview", "").replace("\n", " ").strip()
        user_lines.append(f"From {sender}: {subj} — {preview}")

    user = {
        "role": "user",
        "content": "\n\n".join(user_lines)
    }

    logging.info("💬 Summarizing %d emails…", len(emails))
    try:
        resp = openai_client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[system, user],
            temperature=0.7
        )
    except OpenAIError as e:
        logging.error("⚠️ OpenAI error: %s", e)
        raise RuntimeError(f"OpenAI request failed: {e}")

    return resp.choices[0].message.content