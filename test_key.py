# test_key.py
import os
from dotenv import load_dotenv

load_dotenv()               # reads your .env
print("OPENAI_API_KEY =", os.getenv("OPENAI_API_KEY"))
