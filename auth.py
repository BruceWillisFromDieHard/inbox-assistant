import msal
import os

def get_access_token():
    app = msal.ConfidentialClientApplication(
        os.getenv("CLIENT_ID"),
        authority=f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}",
        client_credential=os.getenv("CLIENT_SECRET")
    )

    result = app.acquire_token_silent(["https://graph.microsoft.com/.default"], account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

    return result["access_token"]