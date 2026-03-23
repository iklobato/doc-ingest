import os
from pathlib import Path

BASE_URL = os.getenv("EVE_API_URL", "https://staging.eve.legal/api")
API_KEY = os.getenv("EVE_API_KEY", "")
USER_EMAIL = os.getenv("USER_EMAIL", "")

FILES_DIR = Path(os.getenv("FILES_DIR", "/app/files"))
INVOICE_PATTERN = os.getenv("INVOICE_PATTERN", "file_*.pdf")
