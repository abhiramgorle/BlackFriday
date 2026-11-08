from __future__ import annotations

import html
import logging
import os

import requests

from .models import Deal

log = logging.getLogger(__name__)

TELEGRAM_LIMIT = 4000  # hard limit is 4096 chars per message

SOURCE_LABEL = {"slickdeals": "Slickdeals", "amazon": "Amazon", "walmart": "Walmart", "page": "Store page"}


def fmt_price(p: float | None) -> str:
    return f"${p:,.2f}" if p is not None else "price n/a"


def deal_line_html(d: Deal) -> str:
    cap = f" (max {fmt_price(d.item.max_price)})" if d.item.max_price is not None else ""
    where = SOURCE_LABEL.get(d.source, d.source)
    if d.store and d.store.lower() not in where.lower():
        where = f"{where} · {d.store}"
    return (
        f"🔥 <b>{html.escape(d.item.name)}</b> — <b>{fmt_price(d.price)}</b>{cap}\n"
        f"{html.escape(d.title[:160])}\n"
        f"{html.escape(where)} · <a href=\"{html.escape(d.url, quote=True)}\">open</a>"
    )


def deal_line_text(d: Deal) -> str:
    where = SOURCE_LABEL.get(d.source, d.source)
    if d.store:
        where = f"{where} / {d.store}"
    return f"{d.item.name}: {fmt_price(d.price)} @ {where}\n{d.title[:160]}\n{d.url}"


def _chunks(lines: list[str], limit: int) -> list[str]:
    out, cur = [], ""
    for ln in lines:
        if cur and len(cur) + len(ln) + 2 > limit:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n\n{ln}" if cur else ln
    if cur:
        out.append(cur)
    return out


class Notifier:
    def __init__(self) -> None:
        self.tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        self.ntfy_topic = os.environ.get("NTFY_TOPIC", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.tg_token and self.tg_chat) or bool(self.ntfy_topic)

    def send_deals(self, deals: list[Deal]) -> bool:
        ok = True
        if self.tg_token and self.tg_chat:
            for msg in _chunks([deal_line_html(d) for d in deals], TELEGRAM_LIMIT):
                ok &= self.telegram(msg)
        if self.ntfy_topic:
            for msg in _chunks([deal_line_text(d) for d in deals], 3800):
                ok &= self.ntfy("Deal alert" if len(deals) == 1 else f"{len(deals)} deal alerts", msg)
        return ok

    def telegram(self, text_html: str) -> bool:
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        try:
            r = requests.post(
                url,
                json={
                    "chat_id": self.tg_chat,
                    "text": text_html,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=20,
            )
            if r.status_code != 200:
                log.error("Telegram error %s: %s", r.status_code, r.text[:300])
                return False
            return True
        except requests.RequestException as e:
            log.error("Telegram request failed: %s", e)
            return False

    def ntfy(self, title: str, body: str) -> bool:
        try:
            r = requests.post(
                f"https://ntfy.sh/{self.ntfy_topic}",
                data=body.encode("utf-8"),
                headers={"Title": title, "Priority": "high", "Tags": "fire"},
                timeout=20,
            )
            if r.status_code != 200:
                log.error("ntfy error %s: %s", r.status_code, r.text[:300])
                return False
            return True
        except requests.RequestException as e:
            log.error("ntfy request failed: %s", e)
            return False

    def telegram_chat_ids(self) -> list[tuple[str, str]]:
        """Return (chat_id, who) pairs seen by the bot. Message the bot first."""
        r = requests.get(f"https://api.telegram.org/bot{self.tg_token}/getUpdates", timeout=20)
        r.raise_for_status()
        seen: dict[str, str] = {}
        for upd in r.json().get("result", []):
            msg = upd.get("message") or upd.get("channel_post") or {}
            chat = msg.get("chat") or {}
            if "id" in chat:
                who = chat.get("username") or chat.get("title") or chat.get("first_name") or chat.get("type", "")
                seen[str(chat["id"])] = who
        return list(seen.items())
