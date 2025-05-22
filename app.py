# app.py
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from auth import get_access_token
from email_utils import fetch_emails_since, analyze_emails

# Load .env
load_dotenv()

app = FastAPI(
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
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # log here as needed
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/summarizeInboxLikeNews")
def summarize_news_style():
    # default: last 12 hours
    from_time = (datetime.utcnow() - timedelta(hours=12)).isoformat() + "Z"
    try:
        emails  = fetch_emails_since(from_time)
        summary = analyze_emails(emails)
        return {"summary": f"🎙️ Here's your inbox broadcast:\n\n{summary}"}
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")