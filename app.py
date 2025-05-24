# app.py
import os
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from auth import get_access_token
from email_utils import fetch_emails_since, analyze_emails, openai_client

# Load and configure
load_dotenv()
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    debug=True,
    title="Inbox Assistant API",
    version="1.0.0",
    servers=[{
        "url": os.getenv("SERVICE_URL", "https://inbox-assistant.onrender.com"),
        "description": "Render Deployment"
    }]
)

class EmailTimeRequest(BaseModel):
    from_time: str

@app.post("/getImportantEmails")
def get_important_emails(req: EmailTimeRequest):
    try:
        emails  = fetch_emails_since(req.from_time, max_messages=200)
        summary = analyze_emails(emails[:50])  # single‐pass for quick endpoint
        return {"summary": summary}
    except Exception as e:
        logging.exception("❌ Error in /getImportantEmails")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/getImportantEmails/stream")
def stream_important_emails(req: EmailTimeRequest):
    """
    1) Page up to 200 emails
    2) Summarize each 50 in turn
    3) Stream a final 2.5–3K word pass back to the client
    """
    try:
        all_emails = fetch_emails_since(req.from_time, max_messages=200)
        # 1st pass: batch summaries
        batches = [
            analyze_emails(all_emails[i : i+50])
            for i in range(0, len(all_emails), 50)
        ]

        def generator():
            system = {
                "role": "system",
                "content": "You are a podcast writer. Turn these batch summaries into a 2,500–3,000 word broadcast."
            }
            user = {
                "role": "user",
                "content": "\n\n".join(f"Batch {i+1}:\n\n{txt}" for i, txt in enumerate(batches))
            }
            stream = openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                messages=[system, user],
                temperature=0.7,
                stream=True
            )
            for chunk in stream:
                piece = chunk.choices[0].delta.get("content")
                if piece:
                    yield piece

        return StreamingResponse(generator(), media_type="text/plain")

    except Exception as e:
        logging.exception("❌ Error in /getImportantEmails/stream")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summarizeInboxLikeNews")
def summarize_news_style():
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=12)).isoformat() + "Z"
        emails = fetch_emails_since(cutoff, max_messages=200)
        summary = analyze_emails(emails[:50])
        return {"summary": f"🎙️ Here's your inbox broadcast:\n\n{summary}"}
    except Exception as e:
        logging.exception("❌ Error in /summarizeInboxLikeNews")
        raise HTTPException(status_code=500, detail=str(e))

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    spec = get_openapi(
        title=app.title,
        version=app.version,
        description="API for summarizing and managing inbox messages",
        routes=app.routes,
    )
    spec["servers"] = [{
        "url": os.getenv("SERVICE_URL", "https://inbox-assistant.onrender.com"),
        "description": "Render Deployment"
    }]
    app.openapi_schema = spec
    return spec

app.openapi = custom_openapi