# Black Friday deal watcher

Checks Slickdeals, Amazon, Walmart and direct store pages for the items in
`watchlist.yaml`, and pushes a Telegram (or ntfy) message to your phone when a
match is at or under your price. Runs for free on GitHub Actions every 30 minutes.

## 1. Telegram bot (2 minutes)

1. In Telegram, open **@BotFather** → `/newbot` → pick a name → copy the token.
2. Open your new bot's chat and send it any message (e.g. `hi`).
3. Get your chat id:

   ```bash
   TELEGRAM_BOT_TOKEN=<token> python run.py chat-id
   ```

## 2. Run locally once

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # paste token + chat id into .env
python run.py test-notify       # a hello message should land on your phone
python run.py once --dry-run    # shows what would be alerted, sends nothing
python run.py once              # sends real alerts and records them in state.json
```

## 3. Run for free on GitHub Actions

1. Push this repo to GitHub.
2. Repo → **Settings → Secrets and variables → Actions → New repository secret**:
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (and optionally `NTFY_TOPIC`).
3. Repo → **Actions** → enable workflows → open **dealwatch** → **Run workflow**
   to test. It then runs every 30 minutes on its own.

The workflow commits `state.json` back to the repo so you never get the same deal
twice. Free minutes: public repo = unlimited; private repo = 2,000 min/month and
this uses ~1,500.

## Alternative: Railway (always-on, ~$5/month)

Railway builds the `Dockerfile` and runs `python run.py loop`. Set the same env
vars in the Railway service plus `INTERVAL_SECONDS` (default 1800). GitHub Actions
does the same job for $0, so Railway is only worth it if you want checks more
often than every ~15 minutes.

## Editing the watchlist

See the comments at the top of `watchlist.yaml`. Each item has `match` words (all
must appear), `exclude` words, `min_price` / `max_price`, and optional direct
`urls`. Commit and push; the next run uses the new list.

## How reliable is each source?

| Source | Covers | Notes |
|---|---|---|
| Slickdeals RSS | Amazon, Walmart, Best Buy, Target, Costco, Newegg, B&H, ... | Public feed, works from any IP. The backbone. |
| Amazon search | Amazon | Works from home IPs; cloud IPs sometimes get a CAPTCHA. Logged and skipped. |
| Walmart search | Walmart | Same as Amazon: occasionally a bot-check page. Logged and skipped. |
| Direct `urls` | Any store page with schema.org JSON-LD (Bambu Lab, Shopify stores, most brands) | Most exact price, per variant. |

## Tests

```bash
python -m pytest -q
```
