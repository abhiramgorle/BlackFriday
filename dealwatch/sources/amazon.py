"""Amazon search results page.

Best effort: Amazon serves a CAPTCHA page to traffic it dislikes (common from cloud
IPs). When that happens we log a warning and return nothing; Slickdeals still
carries Amazon deals.
"""
from __future__ import annotations

import logging
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from ..http import Http
from ..models import Deal, WatchItem, parse_price

log = logging.getLogger(__name__)


def parse_search(html: str, item: WatchItem) -> list[Deal]:
    soup = BeautifulSoup(html, "html.parser")
    deals: list[Deal] = []
    for card in soup.select('div[data-component-type="s-search-result"][data-asin]'):
        asin = card.get("data-asin", "").strip()
        if not asin:
            continue
        h2 = card.select_one("h2")
        title = h2.get_text(" ", strip=True) if h2 else ""
        price_el = card.select_one("span.a-price span.a-offscreen")
        price = parse_price(price_el.get_text(strip=True)) if price_el else None
        if not title:
            continue
        deals.append(
            Deal(
                source="amazon",
                deal_id=asin,
                title=title,
                url=f"https://www.amazon.com/dp/{asin}",
                price=price,
                item=item,
                store="Amazon",
            )
        )
    return deals


def is_blocked(html: str) -> bool:
    low = html.lower()
    return "api-services-support@amazon.com" in low or "enter the characters you see below" in low


def search_amazon(http: Http, item: WatchItem) -> list[Deal]:
    r = http.get(f"https://www.amazon.com/s?k={quote_plus(item.query)}")
    if r is None:
        return []
    if is_blocked(r.text):
        log.warning("amazon[%s]: blocked by CAPTCHA page; skipping", item.name)
        return []
    deals = parse_search(r.text, item)
    log.info("amazon[%s]: %d results", item.name, len(deals))
    return deals
