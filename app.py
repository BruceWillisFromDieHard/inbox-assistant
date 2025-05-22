from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timedelta
from email_utils import fetch_emails_since, analyze_emails

app = FastAPI()  # Required for uvicorn to run

# Request schemas
class EmailTimeRequest(BaseModel):
    from_time: str

class ReplyRequest(BaseModel):
    email_id: str
    message: str

class ArchiveRequest(BaseModel):
    email_id: str

@app.post("/getImportantEmails")
def get_important_emails(request: EmailTimeRequest):
    emails = fetch_emails_since(request.from_time)
    summary = analyze_emails(emails)
    return {"summary": summary}

@app.post("/summarizeInboxLikeNews")
def summarize_news_style():
    from_time = (datetime.utcnow() - timedelta(hours=12)).isoformat()
    emails = fetch_emails_since(from_time)
    summary = analyze_emails(emails)
    return {"summary": f"🎙️ Here's your inbox broadcast:\n\n{summary}"}