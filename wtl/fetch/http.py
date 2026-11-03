"""One polite HTTP client for every outside service.

Wikimedia API etiquette: descriptive User-Agent with contact details, maxlag=5 on Action API
calls, one request at a time (this client is synchronous and never parallel), and back off on
errors, honouring Retry-After.
"""

import sys
import time
from urllib.parse import urlparse

import requests

from ..config import CONTACT, user_agent

_session = None
MIN_INTERVAL = 2.0   # seconds between any two requests; grows after a rate-limit response
MAX_INTERVAL = 15.0
_interval = MIN_INTERVAL
_last = 0.0


class FetchError(RuntimeError):
    pass


def session() -> requests.Session:
    global _session
    if _session is None:
        if not CONTACT:
            raise FetchError("WTL_CONTACT is not set. Wikimedia requires contact details in the "
                             "User-Agent of automated clients; set it to an email address or URL "
                             "where you can be reached, e.g. export WTL_CONTACT=you@example.org. "
                             "Cached results can still be rendered without it.")
        _session = requests.Session()
        _session.headers["User-Agent"] = user_agent()
        _session.headers["Accept-Encoding"] = "gzip"
    return _session


def get_json(url: str, params: dict | None = None, *, timeout: float = 300, retries: int = 8):
    global _last, _interval
    delay = 5.0
    host = urlparse(url).netloc
    for attempt in range(retries):
        wait = _interval - (time.monotonic() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()
        try:
            r = session().get(url, params=params, timeout=timeout)
        except requests.RequestException as e:
            err = f"{type(e).__name__}: {e}"
        else:
            if r.status_code == 200:
                data = r.json()
                # MediaWiki reports maxlag as an API error with HTTP 200.
                if isinstance(data, dict) and data.get("error", {}).get("code") == "maxlag":
                    err = "maxlag"
                    delay = max(delay, float(r.headers.get("Retry-After", 5)))
                else:
                    return data
            elif r.status_code in (429, 500, 502, 503, 504):
                err = f"HTTP {r.status_code} from {host}"
                if r.status_code == 429:  # told to slow down: stay slower for the rest of the run
                    _interval = min(_interval * 2, MAX_INTERVAL)
                ra = r.headers.get("Retry-After")
                if ra and ra.isdigit():
                    delay = max(delay, float(ra))
            else:
                raise FetchError(f"HTTP {r.status_code} for {r.url}: {r.text[:300]}")
        if attempt == retries - 1:
            raise FetchError(f"giving up on {url} after {retries} attempts ({err})")
        print(f"  retrying in {delay:.0f}s ({err}; pacing now {_interval:.0f}s/request)",
              file=sys.stderr)
        time.sleep(delay)
        delay = min(delay * 2, 300)
