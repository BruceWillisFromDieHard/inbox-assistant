import os
import logging
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# SSE support
from sse_starlette.sse import EventSourceResponse

from email_utils import fetch_emails_since, analyze_emails, stream_analyze_emails

# Load environment
load_dotenv()
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    debug=True,
    title="Inbox Assistant API",
    version="1.0.0",
    servers=[{
        "url": os.getenv("SERVICE_URL", "http://localhost:10000"),
        "description": "Deployment URL"
    }]
)

# Allow SSE to work from any origin (adjust in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

class EmailTimeRequest(BaseModel):
    from_time: str

@app.post("/getImportantEmails")
def get_important_emails(req: EmailTimeRequest):
    try:
        emails = fetch_emails_since(req.from_time)
        summary = analyze_emails(emails)
        return JSONResponse({"summary": summary})
    except Exception as e:
        logging.exception("❌ Error in /getImportantEmails")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summarizeInboxLikeNews")
def summarize_news_style():
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=12)).isoformat() + "Z"
        emails = fetch_emails_since(cutoff)
        summary = analyze_emails(emails)
        return JSONResponse({"summary": f"🎙️ Here's your inbox broadcast:\n\n{summary}"})
    except Exception as e:
        logging.exception("❌ Error in /summarizeInboxLikeNews")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/getImportantEmails/stream")
async def get_important_emails_stream(req: EmailTimeRequest, request: Request):
    """
    Stream a long-running summary back in chunks via Server-Sent Events.
    """
    try:
        return EventSourceResponse(
            stream_analyze_emails(req.from_time),
            ping=15
        )
    except Exception as e:
        logging.exception("❌ Error in /getImportantEmails/stream")
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
        "url": os.getenv("SERVICE_URL", "http://localhost:10000"),
        "description": "Deployment URL"
    }]
    app.openapi_schema = spec
    return spec

app.openapi = custom_openapi
