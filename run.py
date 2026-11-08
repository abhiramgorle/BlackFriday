#!/usr/bin/env python3
"""Deal watcher CLI.

  python run.py once                 one pass, send alerts, save state  (GitHub Actions)
  python run.py once --dry-run       one pass, print what would be sent, change nothing
  python run.py loop                 run forever every INTERVAL_SECONDS  (Railway/VPS)
  python run.py test-notify          send a hello message to every configured channel
  python run.py chat-id              print Telegram chat ids the bot has seen
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dealwatch.config import load_config, load_dotenv  # noqa: E402
from dealwatch.notify import Notifier  # noqa: E402
from dealwatch.runner import run_once  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="once", choices=["once", "loop", "test-notify", "chat-id"])
    ap.add_argument("--watchlist", default=str(ROOT / "watchlist.yaml"))
    ap.add_argument("--state", default=str(ROOT / "state.json"))
    ap.add_argument("--dry-run", action="store_true", help="print alerts, do not send or save")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    load_dotenv(ROOT / ".env")

    if args.command == "chat-id":
        n = Notifier()
        if not n.tg_token:
            print("Set TELEGRAM_BOT_TOKEN first.")
            return 2
        ids = n.telegram_chat_ids()
        if not ids:
            print("No chats yet. Open Telegram, send your bot any message, then rerun.")
            return 1
        for cid, who in ids:
            print(f"TELEGRAM_CHAT_ID={cid}   ({who})")
        return 0

    if args.command == "test-notify":
        n = Notifier()
        if not n.configured:
            print("Nothing configured. Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID and/or NTFY_TOPIC.")
            return 2
        ok = True
        if n.tg_token and n.tg_chat:
            ok &= n.telegram("✅ Deal watcher connected. You will get alerts here.")
            print("telegram:", "ok" if ok else "FAILED")
        if n.ntfy_topic:
            r = n.ntfy("Deal watcher", "Connected. You will get alerts here.")
            print("ntfy:", "ok" if r else "FAILED")
            ok &= r
        return 0 if ok else 1

    config = load_config(Path(args.watchlist))
    logging.info("watching %d item(s)", len(config.items))

    if args.command == "once":
        fresh = run_once(config, Path(args.state), dry_run=args.dry_run)
        if args.dry_run:
            print(f"\n{len(fresh)} alert(s) would be sent.")
        return 0

    interval = int(os.environ.get("INTERVAL_SECONDS", "1800"))
    while True:
        try:
            run_once(config, Path(args.state), dry_run=args.dry_run)
        except Exception:  # keep the loop alive on any single-pass failure
            logging.exception("pass failed")
        logging.info("sleeping %ds", interval)
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
