from auth import get_access_token
from dotenv import load_dotenv

load_dotenv()  # ✅ This loads .env vars into os.environ

try:
    token = get_access_token()
    print("✅ Token acquired:", token[:40], "...")
except Exception as e:
    print("❌ Token error:", e)