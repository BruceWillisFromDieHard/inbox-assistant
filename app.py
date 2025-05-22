from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timedelta
from email_utils import fetch_emails_since, analyze_emails
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="Inbox Assistant API",
    version="1.0.0"
)

# ✅ Request schemas
class EmailTimeRequest(BaseModel):
    from_time: str

class ReplyRequest(BaseModel):
    email_id: str
    message: str

class ArchiveRequest(BaseModel):
    email_id: str

# ✅ Routes
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

# ✅ Inject `servers` block manually into the OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Inbox Assistant API",
        version="1.0.0",
        description="API for summarizing and managing inbox messages",
        routes=app.routes,
    )
    openapi_schema["servers"] = [
        {
            "url": "https://inbox-assistant.onrender.com",
            "description": "Render Deployment"
        }
    ]
    app.openapi_schema = openapi_schema
    return openapi_schema

app.openapi = custom_openapi