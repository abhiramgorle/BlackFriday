from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import UrlWatch, WatchItem


@dataclass
class Settings:
    sources: dict[str, bool] = field(
        default_factory=lambda: {"slickdeals": True, "amazon": True, "walmart": True}
    )
    request_delay: float = 1.5


@dataclass
class Config:
    settings: Settings
    items: list[WatchItem]


def load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE lines). Existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(path.read_text()) or {}
    s = raw.get("settings") or {}
    settings = Settings()
    settings.sources.update(s.get("sources") or {})
    settings.request_delay = float(s.get("request_delay", settings.request_delay))

    items: list[WatchItem] = []
    for it in raw.get("items") or []:
        urls = []
        for u in it.get("urls") or []:
            if isinstance(u, str):
                urls.append(UrlWatch(url=u))
            else:
                urls.append(UrlWatch(url=u["url"], variant=u.get("variant")))
        match = [str(w) for w in (it.get("match") or [])]
        if not match and not urls:
            raise ValueError(f"item {it.get('name')!r} needs 'match' words or 'urls'")
        items.append(
            WatchItem(
                name=str(it["name"]),
                match=match,
                exclude=[str(w) for w in (it.get("exclude") or [])],
                max_price=float(it["max_price"]) if it.get("max_price") is not None else None,
                min_price=float(it["min_price"]) if it.get("min_price") is not None else None,
                urls=urls,
            )
        )
    return Config(settings=settings, items=items)
