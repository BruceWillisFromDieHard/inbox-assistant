import os
import logging
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from email_utils import fetch_emails_since, analyze_emails, stream_analyze_emails

# 1. Load .env
load_dotenv()

# 2. Configure logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    debug=True,  # full tracebacks in responses
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
def get_important_emails(request: EmailTimeRequest):
    try:
        emails  = fetch_emails_since(request.from_time)
        summary = analyze_emails(emails)
        return {"summary": summary}
    except Exception as e:
        logging.exception("❌ Error in /getImportantEmails")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/getImportantEmails/stream")
def get_important_emails_stream(request: EmailTimeRequest):
    try:
        emails = fetch_emails_since(request.from_time)
        return StreamingResponse(
            stream_analyze_emails(emails),
            media_type="text/plain; charset=utf-8"
        )
    except Exception as e:
        logging.exception("❌ Error in /getImportantEmails/stream")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/summarizeInboxLikeNews")
def summarize_news_style():
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=12)).isoformat() + "Z"
        emails = fetch_emails_since(cutoff)
        summary = analyze_emails(emails)
        return {"summary": f"🎙️ Here's your inbox broadcast:\n\n{summary}"}
    except Exception as e:
        logging.exception("❌ Error in /summarizeInboxLikeNews")
        raise HTTPException(status_code=500, detail=str(e))


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description="API for summarizing and managing inbox messages",
        routes=app.routes,
    )
    schema["servers"] = [{
        "url": os.getenv("SERVICE_URL", "https://inbox-assistant.onrender.com"),
        "description": "Render Deployment"
    }]
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi