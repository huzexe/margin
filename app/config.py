"""App settings. Values can be overridden with environment variables or a .env file."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def _load_dotenv() -> None:
    """Read KEY=VALUE lines from .env into the environment (existing variables win)."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

DB_PATH = Path(os.environ.get("MARGIN_DB_PATH", BASE_DIR / "data" / "margin.db"))
PORT = int(os.environ.get("MARGIN_PORT", "8000"))

# Phone access over home Wi-Fi: off unless turned on in .env. Other devices need the PIN.
PHONE_ACCESS = os.environ.get("MARGIN_PHONE_ACCESS", "").strip().lower() in ("1", "on", "yes", "true")
PIN = os.environ.get("MARGIN_PIN", "").strip()
HOST = os.environ.get("MARGIN_HOST", "0.0.0.0" if PHONE_ACCESS else "127.0.0.1")
SECRET_PATH = DB_PATH.parent / ".session-secret"  # signs the phone sign-in cookies

# Set by the app launcher: stop by itself when no Margin page has been open for a while
AUTO_STOP = os.environ.get("MARGIN_AUTO_STOP", "").strip().lower() in ("1", "on", "yes", "true")
AUTO_STOP_SECONDS = int(os.environ.get("MARGIN_AUTO_STOP_SECONDS", "180"))

# Text generation (Gemini). The key lives only in .env on this computer.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip()
GEMINI_FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite").strip()
LLM_TIMEOUT_SECONDS = int(os.environ.get("LLM_TIMEOUT_SECONDS", "120"))

# Input limits
MAX_TITLE = 200
MAX_TOPIC = 200
MAX_SUBJECT = 60
MAX_ROUGH_TEXT = 20_000
MAX_CONTENT_BYTES = 1_000_000  # saved enhanced notes (JSON)
MAX_TAG = 30
MAX_TAGS_PER_NOTE = 20
