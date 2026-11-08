"""Direct product page check using schema.org JSON-LD (Product / ProductGroup).

Works on most store product pages, including Bambu Lab's official store, Shopify
stores, and many brand sites. Each variant with an offer becomes a Deal.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterator

from ..http import Http
from ..models import Deal, UrlWatch, WatchItem

log = logging.getLogger(__name__)

_LD_RE = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)


def _iter_ld(html: str) -> Iterator[Any]:
    for m in _LD_RE.finditer(html):
        try:
            data = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            yield from data
        elif isinstance(data, dict) and "@graph" in data:
            yield from data["@graph"]
        else:
            yield data


def _offers(obj: dict) -> list[dict]:
    o = obj.get("offers")
    if isinstance(o, dict):
        return [o]
    if isinstance(o, list):
        return [x for x in o if isinstance(x, dict)]
    return []


def _offer_price(offer: dict) -> float | None:
    for k in ("price", "lowPrice"):
        v = offer.get(k)
        if v is None:
            continue
        try:
            return float(str(v).replace(",", "").replace("$", ""))
        except ValueError:
            continue
    spec = offer.get("priceSpecification")
    if isinstance(spec, dict) and spec.get("price") is not None:
        try:
            return float(str(spec["price"]).replace(",", ""))
        except ValueError:
            pass
    return None


def _in_stock(offer: dict) -> bool:
    a = str(offer.get("availability", "")).lower()
    return not a or "instock" in a or "preorder" in a or "limited" in a


def _products(html: str) -> Iterator[dict]:
    for node in _iter_ld(html):
        if not isinstance(node, dict):
            continue
        t = node.get("@type")
        types = t if isinstance(t, list) else [t]
        if "ProductGroup" in types:
            for v in node.get("hasVariant") or []:
                if isinstance(v, dict):
                    v.setdefault("_group", node.get("name", ""))
                    yield v
        elif "Product" in types:
            yield node


def parse_page(html: str, watch: UrlWatch, item: WatchItem) -> list[Deal]:
    deals: list[Deal] = []
    for prod in _products(html):
        name = str(prod.get("name") or prod.get("_group") or item.name).strip()
        if watch.variant and watch.variant.lower() not in name.lower():
            continue
        for offer in _offers(prod):
            price = _offer_price(offer)
            if price is None:
                continue
            if not _in_stock(offer):
                continue
            url = str(offer.get("url") or prod.get("url") or watch.url)
            sku = str(prod.get("sku") or prod.get("productID") or offer.get("sku") or name)
            deals.append(
                Deal(
                    source="page",
                    deal_id=f"{watch.url}#{sku}",
                    title=name,
                    url=url,
                    price=price,
                    item=item,
                    store=_host(watch.url),
                )
            )
    return deals


def _host(url: str) -> str:
    m = re.match(r"https?://(?:www\.)?([^/]+)", url)
    return m.group(1) if m else ""


def check_page(http: Http, watch: UrlWatch, item: WatchItem) -> list[Deal]:
    r = http.get(watch.url)
    if r is None:
        return []
    deals = parse_page(r.text, watch, item)
    if not deals:
        log.warning("page[%s]: no priced JSON-LD product found at %s", item.name, watch.url)
    else:
        log.info("page[%s]: %d priced variant(s) at %s", item.name, len(deals), _host(watch.url))
    return deals
