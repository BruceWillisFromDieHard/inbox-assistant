import os
import logging
from datetime import datetime
import httpx
from typing import Iterator

from openai import OpenAI, OpenAIError
from auth import get_access_token

# Configure logging at INFO level
logging.basicConfig(level=logging.INFO)

# Base URL for Microsoft Graph
GRAPH_URL = "https://graph.microsoft.com/v1.0"

# Initialize the OpenAI v1 client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# How many emails per chunk for streaming
CHUNK_SIZE = int(os.getenv("EMAIL_CHUNK_SIZE", "10"))

# System prompt
SYSTEM_MSG = {
    "role": "system",
    "content": "You are a concise assistant. Summarize and prioritize these emails."
}


def _parse_iso(dt_str: str) -> datetime | None:
    """
    Parse an ISO8601 string into a datetime.
    Accepts trailing 'Z' or '+00:00'.
    """
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def fetch_emails_since(from_time_iso: str) -> list[dict]:
    """
    Fetch up to 50 emails, then filter locally by cutoff.
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
    r = httpx.get(url, headers=headers, params=params)
    r.raise_for_status()
    items = r.json().get("value", [])

    filtered = []
    for itm in items:
        received = _parse_iso(itm.get("receivedDateTime", ""))
        # make cutoff tz‐aware if necessary
        if received and cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=received.tzinfo)
        if received and received >= cutoff:
            filtered.append(itm)
        else:
            break

    logging.info("✅ %d emails after local filter", len(filtered))
    return filtered


def analyze_emails(emails: list[dict]) -> str:
    """
    One-shot summarization.
    """
    if not emails:
        return "No new emails since that time."

    user_content = []
    for e in emails:
        sender  = e["from"]["emailAddress"]["name"]
        subj    = e.get("subject", "(No subject)")
        preview = e.get("bodyPreview", "").replace("\n", " ").strip()
        user_content.append(f"From {sender}: {subj} — {preview}")

    logging.info("💬 Summarizing %d emails…", len(emails))
    try:
        model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        resp = openai_client.chat.completions.create(
            model=model,
            messages=[SYSTEM_MSG, {"role": "user", "content": "\n\n".join(user_content)}],
            temperature=0.7
        )
    except OpenAIError as e:
        logging.error("⚠️ OpenAI error: %s", e)
        raise RuntimeError(f"OpenAI request failed: {e}")

    return resp.choices[0].message.content


def stream_analyze_emails(emails: list[dict]) -> Iterator[str]:
    """
    Stream summaries in CHUNK_SIZE batches.
    """
    if not emails:
        yield "No new emails since that time."
        return

    batches = [emails[i : i + CHUNK_SIZE] for i in range(0, len(emails), CHUNK_SIZE)]
    for idx, batch in enumerate(batches, start=1):
        header = f"\n--- Chunk {idx}/{len(batches)} ---\n"
        yield header

        user_content = "\n\n".join(
            f"From {e['from']['emailAddress']['name']}: "
            f"{e.get('subject','(No subject)')} — "
            f"{e.get('bodyPreview','').replace(chr(10),' ')}"
            for e in batch
        )

        logging.info("📡 Streaming chunk %d/%d…", idx, len(batches))
        try:
            model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
            stream = openai_client.chat.completions.create(
                model=model,
                messages=[SYSTEM_MSG, {"role": "user", "content": user_content}],
                temperature=0.7,
                stream=True
            )
        except OpenAIError as e:
            logging.error("⚠️ OpenAI stream error: %s", e)
            raise RuntimeError(f"OpenAI stream failed: {e}")

        for delta in stream:
            token = delta.choices[0].delta.get("content")
            if token:
                yield token