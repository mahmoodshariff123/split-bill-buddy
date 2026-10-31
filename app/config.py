import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("SPLITBILL_DATA", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
SAMPLES_DIR = ROOT / "samples"

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_API_BASE = os.getenv("PAYPAL_API_BASE", "https://api-m.sandbox.paypal.com")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
# Tried in order when the main model is busy or unavailable.
GEMINI_FALLBACKS = ["gemini-2.5-flash-lite", "gemini-flash-latest"]


def paypal_live() -> bool:
    return bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET)


def ai_live() -> bool:
    return bool(GEMINI_API_KEY)
