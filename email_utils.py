# email_utils.py
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

# How many emails per OpenAI call (default 25)
CHUNK_SIZE = int(os.getenv("EMAIL_CHUNK_SIZE", "25"))

# Initialize the OpenAI v1 client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _parse_iso(dt_str: str) -> datetime | None:
    """
    Parse an ISO8601 string into a datetime.
    Accepts strings ending with 'Z' or with an offset.
    """
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def fetch_emails_since(from_time_iso: str) -> list[dict]:
    """
    Fetch the latest 200 emails from the user's Inbox, then filter
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
        "$top": 200,
        "$select": "subject,receivedDateTime,from,bodyPreview"
    }

    logging.info("📬 Fetching up to 200 inbox messages…")
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

    logging.info("✅ Fetched %d emails after filter", len(filtered))
    return filtered


def analyze_emails(emails: list[dict]) -> str:
    """
    Break into CHUNK_SIZE chunks, summarize each, then stitch together.
    """
    if not emails:
        return "No new emails since that time."

    # Split into chunks
    chunks = [
        emails[i : i + CHUNK_SIZE]
        for i in range(0, len(emails), CHUNK_SIZE)
    ]

    summaries = []
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        # build messages
        system_msg = {
            "role": "system",
            "content": "You are a concise assistant. Summarize and prioritize these emails."
        }
        user_content = "\n\n".join(
            f"From {e.get('from', {}).get('emailAddress', {}).get('name','Unknown')}: "
            f"{e.get('subject','(No subject)')} — "
            f"{e.get('bodyPreview','').replace('\\n',' ')}"
            for e in chunk
        )
        user_msg = {"role": "user", "content": user_content}

        logging.info("💬 Summarizing chunk %d/%d via OpenAI…", idx, total)
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

        text = resp.choices[0].message.content
        summaries.append(f"--- Chunk {idx}/{total} ---\n{text}")

    return "\n\n".join(summaries)