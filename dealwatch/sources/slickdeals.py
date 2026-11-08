"""Slickdeals keyword search via its public RSS feed.

Slickdeals aggregates deals from Amazon, Walmart, Best Buy, Target, Costco, Newegg,
B&H and hundreds more, so this one source covers most Black Friday postings.
"""
from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

from ..http import Http
from ..models import Deal, WatchItem, parse_price

log = logging.getLogger(__name__)

_STORE_RE = re.compile(r"\bat\s+([A-Z][\w&.'\- ]{1,30}?)(?:\s*[\(\[]|\s*$|\s*\+|\s*-\s|\s*\|)")
MAX_AGE_DAYS = 10  # older posts are almost always expired


def _feed_url(query: str) -> str:
    return (
        "https://slickdeals.net/newsearch.php?src=SearchBarV2"
        f"&q={quote_plus(query)}&searcharea=deals&searchin=first&rss=1"
    )


def _too_old(pub: str | None, now: float) -> bool:
    if not pub:
        return False
    try:
        ts = parsedate_to_datetime(pub).timestamp()
    except (TypeError, ValueError):
        return False
    return now - ts > MAX_AGE_DAYS * 86400


def parse_feed(xml_text: str, item: WatchItem, now: float | None = None) -> list[Deal]:
    now = time.time() if now is None else now
    deals: list[Deal] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log.warning("Slickdeals feed parse error: %s", e)
        return deals
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        guid = (node.findtext("guid") or link).strip()
        if not title or not link:
            continue
        if _too_old(node.findtext("pubDate"), now):
            continue
        store = ""
        m = _STORE_RE.search(title)
        if m:
            store = m.group(1).strip()
        deals.append(
            Deal(
                source="slickdeals",
                deal_id=guid.rsplit("/", 1)[-1] or guid,
                title=title,
                url=link,
                price=parse_price(title),
                item=item,
                store=store,
            )
        )
    return deals


def search_slickdeals(http: Http, item: WatchItem) -> list[Deal]:
    r = http.get(_feed_url(item.query))
    if r is None:
        return []
    deals = parse_feed(r.text, item)
    log.info("slickdeals[%s]: %d results", item.name, len(deals))
    return deals
