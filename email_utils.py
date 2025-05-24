import os
import logging
from datetime import datetime
import httpx
from openai import OpenAI, OpenAIError
from sse_starlette import EventSourceResponse
from auth import get_access_token

logging.basicConfig(level=logging.INFO)

GRAPH_URL = "https://graph.microsoft.com/v1.0"
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# How many emails per API call (max 200), then we'll chunk by EMAIL_CHUNK_SIZE
MAX_EMAILS = int(os.getenv("EMAIL_MAX_MESSAGES", "200"))
CHUNK_SIZE = int(os.getenv("EMAIL_CHUNK_SIZE", "25"))


def _parse_iso(dt_str: str) -> datetime | None:
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def fetch_emails_since(from_time_iso: str, max_messages: int = MAX_EMAILS) -> list[dict]:
    cutoff = _parse_iso(from_time_iso)
    if cutoff is None:
        raise ValueError(f"Invalid from_time: {from_time_iso}")

    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GRAPH_URL}/users/{os.getenv('USER_ID')}/mailFolders/Inbox/messages"
    params = {
        "$orderby": "receivedDateTime desc",
        "$top": max_messages,
        "$select": "subject,receivedDateTime,from,bodyPreview"
    }

    logging.info("📬 Fetching inbox batch (up to %d)…", max_messages)
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

    logging.info("✅ %d emails after filter", len(filtered))
    return filtered


def analyze_emails(emails: list[dict]) -> str:
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

    user_msg = {"role": "user", "content": "\n\n".join(user_items)}

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


def stream_analyze_emails(request_from_time: str):
    """
    SSE generator: fetch up to MAX_EMAILS, split into CHUNK_SIZE batches,
    summarize each, and yield as events.
    """
    emails = fetch_emails_since(request_from_time)
    total = len(emails)
    logging.info("🔀 Streaming summary in chunks of %d…", CHUNK_SIZE)

    for i in range(0, total, CHUNK_SIZE):
        batch = emails[i : i + CHUNK_SIZE]
        summary = analyze_emails(batch)
        yield {"event": "chunk", "data": summary}

    yield {"event": "done", "data": f"All {total} emails summarized."}