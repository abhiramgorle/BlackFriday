from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from .models import Deal

RETENTION_DAYS = 45


class State:
    """Remembers what was already alerted so the same deal is not sent twice.

    A deal is alerted again only if its price drops below the last alerted price.
    """

    def __init__(self, path: Path):
        self.path = path
        self.alerted: dict[str, dict] = {}
        if path.exists():
            try:
                self.alerted = json.loads(path.read_text()).get("alerted", {})
            except json.JSONDecodeError:
                self.alerted = {}

    def should_alert(self, deal: Deal) -> bool:
        prev = self.alerted.get(deal.key)
        if prev is None:
            return True
        prev_price: Optional[float] = prev.get("price")
        if deal.price is None or prev_price is None:
            return False
        return deal.price < prev_price - 0.009

    def record(self, deal: Deal) -> None:
        self.alerted[deal.key] = {
            "price": deal.price,
            "title": deal.title[:120],
            "ts": int(time.time()),
        }

    def save(self) -> None:
        cutoff = time.time() - RETENTION_DAYS * 86400
        self.alerted = {k: v for k, v in self.alerted.items() if v.get("ts", 0) >= cutoff}
        self.path.write_text(json.dumps({"alerted": self.alerted}, indent=1, sort_keys=True) + "\n")
