from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timedelta
from email_utils import fetch_emails_since, analyze_emails

# ✅ Add OpenAPI `servers` block so GPT knows where to send requests
app = FastAPI(
    title="Inbox Assistant API",
    version="1.0.0",
    servers=[
        {
            "url": "https://inbox-assistant.onrender.com",
            "description": "Production Render Deployment"
        }
    ]
)

# ✅ Request schemas
class EmailTimeRequest(BaseModel):
    from_time: str

class ReplyRequest(BaseModel):
    email_id: str
    message: str

class ArchiveRequest(BaseModel):
    email_id: str

# ✅ Route: Pull and summarize emails since a given timestamp
@app.post("/getImportantEmails")
def get_important_emails(request: EmailTimeRequest):
    emails = fetch_emails_since(request.from_time)
    summary = analyze_emails(emails)
    return {"summary": summary}

# ✅ Route: Provide a morning-style inbox news summary
@app.post("/summarizeInboxLikeNews")
def summarize_news_style():
    from_time = (datetime.utcnow() - timedelta(hours=12)).isoformat()
    emails = fetch_emails_since(from_time)
    summary = analyze_emails(emails)
    return {"summary": f"🎙️ Here's your inbox broadcast:\n\n{summary}"}