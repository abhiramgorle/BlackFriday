from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

_PRICE_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d{2}))?")


def parse_price(text: str | None) -> Optional[float]:
    """Return the first dollar amount found in text, or None."""
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    whole = m.group(1).replace(",", "")
    cents = m.group(2) or "00"
    try:
        return float(f"{whole}.{cents}")
    except ValueError:
        return None


@dataclass
class UrlWatch:
    url: str
    variant: Optional[str] = None


@dataclass
class WatchItem:
    name: str
    match: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    max_price: Optional[float] = None
    min_price: Optional[float] = None  # filters out accessories (pints, nozzles, books)
    urls: list[UrlWatch] = field(default_factory=list)

    @property
    def query(self) -> str:
        return " ".join(self.match)

    def title_matches(self, title: str) -> bool:
        t = title.lower()
        if not all(w.lower() in t for w in self.match):
            return False
        return not any(w.lower() in t for w in self.exclude)

    def price_ok(self, price: Optional[float]) -> bool:
        if self.max_price is None and self.min_price is None:
            return True
        if price is None:
            return False
        if self.max_price is not None and price > self.max_price:
            return False
        if self.min_price is not None and price < self.min_price:
            return False
        return True


@dataclass
class Deal:
    source: str          # "slickdeals", "amazon", "walmart", "page"
    deal_id: str         # stable id within the source
    title: str
    url: str
    price: Optional[float]
    item: WatchItem
    store: str = ""      # merchant name when known (Slickdeals carries it)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.deal_id}"
