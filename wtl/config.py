"""Paths and HTTP identity. Everything configurable lives here."""

import os
from pathlib import Path

from . import __version__

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(os.environ.get("WTL_CACHE", ROOT / "cache"))
OUT_DIR = Path(os.environ.get("WTL_OUT", ROOT / "out"))
DATA_DIR = ROOT / "data"
SANCTIONS_CSV = DATA_DIR / "sanctions.csv"
ARTICLES_CSV = DATA_DIR / "articles.csv"

WIKI = "en.wikipedia.org"
API_URL = f"https://{WIKI}/w/api.php"
WIKIWHO_URL = "https://wikiwho-api.wmcloud.org/en/api/v1.0.0-beta"

# Wikimedia asks automated clients for a User-Agent with contact details.
# Set WTL_CONTACT to an email address or URL where you can be reached.
# The environment variable wins; otherwise a local, git-ignored file `.wtl-contact` is read.
CONTACT = os.environ.get("WTL_CONTACT", "").strip()
if not CONTACT and (ROOT / ".wtl-contact").exists():
    CONTACT = (ROOT / ".wtl-contact").read_text(encoding="utf-8").strip()


def user_agent() -> str:
    return f"WikipediaTransparencyLayer/{__version__} (read-only research tool; {CONTACT})"
