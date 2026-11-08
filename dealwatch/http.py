from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


class Http:
    """One shared session with polite pacing between requests."""

    def __init__(self, delay: float = 1.5, timeout: float = 25.0):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.delay = delay
        self.timeout = timeout
        self._last = 0.0

    def get(self, url: str, **kw) -> requests.Response | None:
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        try:
            r = self.session.get(url, timeout=self.timeout, **kw)
        except requests.RequestException as e:
            log.warning("GET %s failed: %s", url, e)
            return None
        finally:
            self._last = time.monotonic()
        if r.status_code != 200:
            log.warning("GET %s -> HTTP %s", url, r.status_code)
            return None
        return r
