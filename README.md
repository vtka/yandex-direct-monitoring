# Yandex Direct Monitor

Daily Yandex Direct campaign reports delivered straight to Telegram.

**Free. Secure. Zero dependencies.**

```
┌──────────────────────────────────────────────┐
│  Yandex Direct — Yesterday                   │
│                                              │
│  Impressions    12 450                       │
│  Clicks            312                       │
│  Spend          4 870.50 ₽                   │
│  CTR              2.51%                      │
│  Avg. CPC        15.61 ₽                    │
│                                              │
│  ▸ Brand Campaign                            │
│    8 200 impressions · 245 clicks · 3 100 ₽  │
│  ▸ Retargeting                               │
│    4 250 impressions · 67 clicks · 1 770 ₽   │
└──────────────────────────────────────────────┘
```

## How It Works

| | |
|---|---|
| **Schedule** | Daily at 9:00 AM MSK, weekly summary on Mondays |
| **Data** | Impressions, clicks, spend, CTR, CPC per campaign |
| **Delivery** | Telegram group or private chat |
| **Cost** | $0 — GitHub Actions free tier + Telegram Bot API |
| **Dependencies** | None — Python standard library only |
| **Security** | Secrets stored in GitHub, never in code |

## Quick Start

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token
2. Add the bot to your group
3. Get the group `chat_id`:
   ```
   curl https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
   Send any message to the group, then find `"chat":{"id":-123456789}` in the response

### 2. Deploy

Fork or clone this repo, then add three **repository secrets**:

> **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `YANDEX_DIRECT_TOKEN` | Your Yandex Direct OAuth token |
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Chat/group ID (negative for groups) |

### 3. Verify

**Actions → Yandex Direct Report → Run workflow** → check "Send a test notification"

## Usage

Reports are sent automatically on schedule. You can also trigger them manually:

| Method | How |
|---|---|
| **GitHub Actions** | Run workflow → choose `daily` or `weekly` |
| **Local** | `YANDEX_DIRECT_TOKEN=... TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 check_campaigns.py` |
| **Custom period** | Set `REPORT_TYPE=weekly` env var for 7-day summary |

## Architecture

```
GitHub Actions (cron)
       │
       ▼
 Yandex Direct API ──── Reports endpoint (TSV)
       │
       ▼
 check_campaigns.py ─── Parse & format
       │
       ▼
 Telegram Bot API ───── Send to group
```

## License

MIT
