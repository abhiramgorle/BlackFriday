"""Walmart search results page (reads the embedded __NEXT_DATA__ JSON).

Best effort: Walmart shows a "Robot or human?" page to traffic it dislikes. We log
a warning and return nothing in that case; Slickdeals still carries Walmart deals.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterator
from urllib.parse import quote_plus

from ..http import Http
from ..models import Deal, WatchItem

log = logging.getLogger(__name__)

_NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _walk_products(node: Any) -> Iterator[dict]:
    if isinstance(node, dict):
        if "usItemId" in node and "name" in node and "priceInfo" in node:
            yield node
            return
        for v in node.values():
            yield from _walk_products(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_products(v)


def _price_of(p: dict) -> float | None:
    v = p.get("price")
    if isinstance(v, (int, float)) and v > 0:
        return float(v)
    if isinstance(v, str):
        try:
            f = float(v.replace("$", "").replace(",", ""))
            if f > 0:
                return f
        except ValueError:
            pass
    details = (p.get("priceInfo") or {}).get("priceDetails") or {}
    for line in details.get("priceLines") or []:
        for val in line.get("values") or []:
            if val.get("key") == "PRICE":
                try:
                    return float(str(val.get("value")).replace(",", ""))
                except (TypeError, ValueError):
                    continue
    return None


def parse_search(html: str, item: WatchItem) -> list[Deal] | None:
    """Return deals, or None when the page carried no product JSON (blocked)."""
    m = _NEXT_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    seen: set[str] = set()
    deals: list[Deal] = []
    for p in _walk_products(data):
        pid = str(p["usItemId"])
        if pid in seen:
            continue
        seen.add(pid)
        if p.get("isOutOfStock") is True:
            continue
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        path = p.get("canonicalUrl") or f"/ip/{pid}"
        url = path if path.startswith("http") else f"https://www.walmart.com{path}"
        if "/ip/" in url and pid not in url:
            url = f"https://www.walmart.com/ip/{pid}"
        deals.append(
            Deal(
                source="walmart",
                deal_id=pid,
                title=name,
                url=url.split("?")[0],
                price=_price_of(p),
                item=item,
                store=str(p.get("sellerName") or "Walmart"),
            )
        )
    return deals


def search_walmart(http: Http, item: WatchItem) -> list[Deal]:
    r = http.get(f"https://www.walmart.com/search?q={quote_plus(item.query)}")
    if r is None:
        return []
    deals = parse_search(r.text, item)
    if deals is None:
        log.warning("walmart[%s]: no product data (bot check page?); skipping", item.name)
        return []
    log.info("walmart[%s]: %d results", item.name, len(deals))
    return deals
