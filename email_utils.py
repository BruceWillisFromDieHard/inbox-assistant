import os
import logging
from datetime import datetime, timezone
import httpx
from openai import OpenAI, OpenAIError

from auth import get_access_token

# Configure logging
logging.basicConfig(level=logging.INFO)

# Microsoft Graph base URL
GRAPH_URL = "https://graph.microsoft.com/v1.0"

# OpenAI v1 client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _parse_iso(dt_str: str) -> datetime | None:
    """
    Parse an ISO8601 timestamp into a timezone-aware datetime (UTC).
    - If it ends with 'Z', convert to '+00:00'.
    - If it has no offset at all, assume UTC.
    Returns None on parse failure.
    """
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        # if no offset and no 'Z', assume UTC
        elif "+" not in dt_str and "-" not in dt_str[10:]:
            dt_str += "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception as e:
        logging.warning("Failed to parse datetime %r: %s", dt_str, e)
        return None


def fetch_emails_since(from_time_iso: str) -> list[dict]:
    """
    Fetch up to 50 messages from Inbox, then locally filter to >= cutoff.
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
        "$select": "subject,receivedDateTime,from,bodyPreview",
    }

    logging.info("📬 Fetching inbox batch without filter…")
    r = httpx.get(url, headers=headers, params=params)
    r.raise_for_status()

    items = r.json().get("value", [])
    filtered = []
    for msg in items:
        rec = _parse_iso(msg.get("receivedDateTime", ""))  # always aware
        if rec and rec >= cutoff:
            filtered.append(msg)
        else:
            break

    logging.info("✅ %d emails after local filter", len(filtered))
    return filtered


def analyze_emails(emails: list[dict]) -> str:
    """
    Non-streaming summary via OpenAI.
    """
    if not emails:
        return "No new emails since that time."

    system_msg = {
        "role": "system",
        "content": "You are a concise assistant. Summarize and prioritize these emails."
    }
    user_lines = []
    for e in emails:
        sender = e.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
        subj   = e.get("subject", "(No subject)")
        prev   = e.get("bodyPreview", "").replace("\n", " ").strip()
        user_lines.append(f"From {sender}: {subj} — {prev}")

    user_msg = {"role": "user", "content": "\n\n".join(user_lines)}

    logging.info("💬 Summarizing %d emails via OpenAI…", len(emails))
    try:
        model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        resp = openai_client.chat.completions.create(
            model=model,
            messages=[system_msg, user_msg],
            temperature=0.7
        )
    except OpenAIError as ex:
        logging.error("⚠️ OpenAI error: %s", ex)
        raise RuntimeError(f"OpenAI request failed: {ex}")

    return resp.choices[0].message.content


def stream_summarize_emails(emails: list[dict], model: str, temperature: float):
    """
    Yield tokens directly from OpenAI's streaming chat completion.
    """
    system_msg = {"role": "system", "content": "You are a concise assistant. Summarize and prioritize these emails."}
    user_msg   = {"role": "user",   "content": "\n\n".join(
        f"From {e.get('from',{}).get('emailAddress',{}).get('name','Unknown')}: "
        f"{e.get('subject','(No subject)')} — "
        f"{e.get('bodyPreview','').replace('\\n',' ').strip()}"
        for e in emails
    )}

    logging.info("💬 Starting OpenAI streaming for %d emails…", len(emails))
    try:
        stream = openai_client.chat.completions.create(
            model=model,
            messages=[system_msg, user_msg],
            temperature=temperature,
            stream=True
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.get("content")
            if delta:
                yield delta
    except OpenAIError as ex:
        logging.error("⚠️ OpenAI streaming error: %s", ex)
        yield f"\n\nError: {ex}"