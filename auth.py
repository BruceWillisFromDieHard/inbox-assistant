# auth.py
import os
from dotenv import load_dotenv
load_dotenv()   # ← make sure .env is loaded before any getenv()

import msal
import logging

def get_access_token() -> str:
    """
    Acquire an Azure AD v2.0 access token for Microsoft Graph using
    client credentials from environment variables.
    """
    client_id     = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    tenant_id     = os.getenv("TENANT_ID")

    if not all([client_id, client_secret, tenant_id]):
        logging.error("Missing one or more required Azure credentials: "
                      "CLIENT_ID=%r, CLIENT_SECRET=%r, TENANT_ID=%r",
                      client_id, client_secret, tenant_id)
        raise RuntimeError("CLIENT_ID, CLIENT_SECRET and TENANT_ID must be set in the environment")

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )

    scopes = ["https://graph.microsoft.com/.default"]
    result = app.acquire_token_silent(scopes, account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=scopes)

    if "access_token" not in result:
        err = result.get("error_description") or result
        logging.error("Failed to acquire token: %s", err)
        raise RuntimeError(f"Failed to acquire token: {err}")

    return result["access_token"]