#!/usr/bin/env python3
"""Yandex Direct daily campaign report → Telegram."""

import json
import os
import re
import ssl
import time
import urllib.request

API_BASE = "https://api.direct.yandex.com/json/v5"
YANDEX_TOKEN = os.environ["YANDEX_DIRECT_TOKEN"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

CURRENCY_SYMBOLS = {
    "RUB": "₽", "KZT": "₸", "BYN": "Br", "USD": "$",
    "EUR": "€", "CHF": "Fr", "TRY": "₺", "UAH": "₴",
}


def yandex_api(service, method, params):
    """Call Yandex Direct JSON API v5."""
    url = f"{API_BASE}/{service}"
    body = json.dumps({"method": method, "params": params}).encode()
    headers = {
        "Authorization": f"Bearer {YANDEX_TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept-Language": "ru",
    }
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=body, headers=headers)
    resp = urllib.request.urlopen(req, timeout=30, context=ctx)
    return json.loads(resp.read().decode())["result"]


def get_currency_symbol():
    """Get account currency symbol from Yandex Direct API."""
    try:
        result = yandex_api("clients", "get", {
            "FieldNames": ["Currency"]
        })
        currency = result["Clients"][0]["Currency"]
        return CURRENCY_SYMBOLS.get(currency, currency)
    except Exception:
        return "₸"


def yandex_report(date_range, fields, report_type="CAMPAIGN_PERFORMANCE_REPORT"):
    """Fetch a report from Yandex Direct Reports API."""
    url = f"{API_BASE}/reports"
    body = json.dumps({"params": {
        "SelectionCriteria": {},
        "FieldNames": fields,
        "ReportName": f"tg-report-{int(time.time())}",
        "ReportType": report_type,
        "DateRangeType": date_range,
        "Format": "TSV",
        "IncludeVAT": "YES",
    }}).encode()

    headers = {
        "Authorization": f"Bearer {YANDEX_TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept-Language": "ru",
        "processingMode": "auto",
        "returnMoneyInMicros": "false",
        "skipReportHeader": "true",
        "skipReportSummary": "true",
    }

    ctx = ssl.create_default_context()
    for attempt in range(10):
        req = urllib.request.Request(url, data=body, headers=headers)
        resp = urllib.request.urlopen(req, timeout=120, context=ctx)
        if resp.status in (200, 201):
            return resp.read().decode("utf-8")
        if resp.status == 202:
            wait = int(resp.headers.get("retryIn", 5))
            print(f"Report processing, retry in {wait}s...")
            time.sleep(wait)
            continue
        raise RuntimeError(f"Yandex API error {resp.status}: {resp.read().decode()}")

    raise RuntimeError("Report not ready after 10 retries")


def parse_tsv(tsv_text, fields):
    """Parse TSV report into list of dicts."""
    rows = []
    for line in tsv_text.strip().split("\n"):
        if not line or line.startswith(fields[0]):
            continue
        parts = line.split("\t")
        if len(parts) == len(fields):
            rows.append(dict(zip(fields, parts)))
    return rows


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10)


def fmt_number(val):
    """Format number with spaces as thousands separator."""
    try:
        n = float(val)
        if n == int(n):
            return f"{int(n):,}".replace(",", " ")
        return f"{n:,.2f}".replace(",", " ")
    except (ValueError, TypeError):
        return val


def fmt_cost(val, symbol="₸"):
    """Format cost value with currency symbol."""
    try:
        return f"{float(val):,.2f} {symbol}".replace(",", " ")
    except (ValueError, TypeError):
        return val


def clean_campaign_name(name):
    """Remove domain suffixes from campaign names to prevent Telegram auto-linking."""
    return re.sub(r'\s*—\s*([\w-]+\.[\w]+)$', '', name)


def build_daily_message(rows, symbol, period="Вчера"):
    """Build Telegram message for daily campaign report."""
    if not rows:
        return f"📊 <b>Яндекс Директ — {period}</b>\n\nНет данных за этот период."

    total_impressions = sum(int(r.get("Impressions", 0)) for r in rows)
    total_clicks = sum(int(r.get("Clicks", 0)) for r in rows)
    total_cost = sum(float(r.get("Cost", 0)) for r in rows)
    total_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    avg_cpc = (total_cost / total_clicks) if total_clicks > 0 else 0

    lines = [
        f"📊 <b>Яндекс Директ — {period}</b>",
        "",
        f"Показы: <b>{fmt_number(total_impressions)}</b>",
        f"Клики: <b>{fmt_number(total_clicks)}</b>",
        f"Расход: <b>{fmt_cost(total_cost, symbol)}</b>",
        f"CTR: <b>{total_ctr:.2f}%</b>",
        f"Ср. цена клика: <b>{fmt_cost(avg_cpc, symbol)}</b>",
    ]

    if len(rows) > 1:
        lines += ["", "📋 <b>По кампаниям:</b>"]

    for r in sorted(rows, key=lambda x: float(x.get("Cost", 0)), reverse=True):
        cost = float(r.get("Cost", 0))
        clicks = int(r.get("Clicks", 0))
        impressions = int(r.get("Impressions", 0))
        if impressions == 0 and clicks == 0:
            continue
        name = clean_campaign_name(r.get("CampaignName", "—"))
        lines.append(
            f"\n▸ <b>{name}</b>\n"
            f"  {fmt_number(impressions)} показов · "
            f"{fmt_number(clicks)} кликов · "
            f"{fmt_cost(cost, symbol)}"
        )

    return "\n".join(lines)


def build_weekly_message(rows, symbol):
    """Build Telegram message for weekly summary."""
    if not rows:
        return "📈 <b>Яндекс Директ — Неделя</b>\n\nНет данных за неделю."

    total_impressions = sum(int(r.get("Impressions", 0)) for r in rows)
    total_clicks = sum(int(r.get("Clicks", 0)) for r in rows)
    total_cost = sum(float(r.get("Cost", 0)) for r in rows)
    total_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    avg_cpc = (total_cost / total_clicks) if total_clicks > 0 else 0

    lines = [
        "📈 <b>Яндекс Директ — Неделя</b>",
        "",
        f"Показы: <b>{fmt_number(total_impressions)}</b>",
        f"Клики: <b>{fmt_number(total_clicks)}</b>",
        f"Расход: <b>{fmt_cost(total_cost, symbol)}</b>",
        f"CTR: <b>{total_ctr:.2f}%</b>",
        f"Ср. цена клика: <b>{fmt_cost(avg_cpc, symbol)}</b>",
    ]

    campaigns = {}
    for r in rows:
        name = r.get("CampaignName", "—")
        if name not in campaigns:
            campaigns[name] = {"impressions": 0, "clicks": 0, "cost": 0.0}
        campaigns[name]["impressions"] += int(r.get("Impressions", 0))
        campaigns[name]["clicks"] += int(r.get("Clicks", 0))
        campaigns[name]["cost"] += float(r.get("Cost", 0))

    if len(campaigns) > 1:
        lines += ["", "📋 <b>По кампаниям:</b>"]

    for name, data in sorted(campaigns.items(), key=lambda x: x[1]["cost"], reverse=True):
        if data["impressions"] == 0 and data["clicks"] == 0:
            continue
        name = clean_campaign_name(name)
        lines.append(
            f"\n▸ <b>{name}</b>\n"
            f"  {fmt_number(data['impressions'])} показов · "
            f"{fmt_number(data['clicks'])} кликов · "
            f"{fmt_cost(data['cost'], symbol)}"
        )

    return "\n".join(lines)


def main():
    report_type = os.environ.get("REPORT_TYPE", "daily")

    if os.environ.get("TEST_MODE") == "true":
        symbol = get_currency_symbol()
        send_telegram(
            "🧪 <b>Тестовое уведомление</b>\n"
            "\n"
            "Мониторинг Яндекс Директ настроен.\n"
            f"Валюта аккаунта: <b>{symbol}</b>\n"
            "\n"
            "📊 <b>Пример сводки:</b>\n"
            "Показы: <b>1 234</b>\n"
            "Клики: <b>56</b>\n"
            f"Расход: <b>789.00 {symbol}</b>\n"
            "CTR: <b>4.54%</b>"
        )
        print("Test notification sent.")
        return

    symbol = get_currency_symbol()
    fields = ["CampaignName", "Impressions", "Clicks", "Cost", "Ctr", "AvgCpc"]

    if report_type == "weekly":
        date_range = "LAST_7_DAYS"
        tsv = yandex_report(date_range, fields)
        rows = parse_tsv(tsv, fields)
        msg = build_weekly_message(rows, symbol)
    elif report_type == "today":
        date_range = "TODAY"
        tsv = yandex_report(date_range, fields)
        rows = parse_tsv(tsv, fields)
        msg = build_daily_message(rows, symbol, period="Сегодня")
    else:
        date_range = "YESTERDAY"
        tsv = yandex_report(date_range, fields)
        rows = parse_tsv(tsv, fields)
        msg = build_daily_message(rows, symbol)

    send_telegram(msg)
    print(f"Report sent ({report_type}, {len(rows)} campaign rows, currency: {symbol})")


if __name__ == "__main__":
    main()
