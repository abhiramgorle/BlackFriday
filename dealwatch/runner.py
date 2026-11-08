from __future__ import annotations

import logging
from pathlib import Path

from .config import Config
from .http import Http
from .models import Deal
from .notify import Notifier
from .sources import check_page, search_amazon, search_slickdeals, search_walmart
from .state import State

log = logging.getLogger(__name__)


def collect(config: Config) -> list[Deal]:
    """Fetch every source for every item and return deals that pass the filters."""
    http = Http(delay=config.settings.request_delay)
    src = config.settings.sources
    hits: list[Deal] = []
    for item in config.items:
        found: list[Deal] = []
        if item.match:
            if src.get("slickdeals", True):
                found += search_slickdeals(http, item)
            if src.get("amazon", True):
                found += search_amazon(http, item)
            if src.get("walmart", True):
                found += search_walmart(http, item)
        for w in item.urls:
            found += check_page(http, w, item)

        for d in found:
            # Direct URL watches are trusted to be the right product; only the
            # price gate applies. Search results must also match the title words.
            if d.source != "page" and not item.title_matches(d.title):
                continue
            if not item.price_ok(d.price):
                continue
            hits.append(d)
    return hits


def run_once(config: Config, state_path: Path, dry_run: bool = False) -> list[Deal]:
    """One full pass. Returns the deals that were (or would be) alerted."""
    state = State(state_path)
    notifier = Notifier()
    hits = collect(config)
    fresh = [d for d in hits if state.should_alert(d)]
    log.info("%d matching deal(s), %d new", len(hits), len(fresh))

    if not fresh:
        return []
    for d in fresh:
        log.info("NEW  %-22s %9s  %s  %s", d.item.name, f"${d.price:,.2f}" if d.price else "n/a", d.source, d.title[:70])

    if dry_run:
        return fresh
    if not notifier.configured:
        log.error("No notifier configured (TELEGRAM_BOT_TOKEN+TELEGRAM_CHAT_ID or NTFY_TOPIC). Not saving state.")
        return fresh
    if notifier.send_deals(fresh):
        for d in fresh:
            state.record(d)
        state.save()
    else:
        log.error("Notification failed; state not saved so these deals retry next run.")
    return fresh
