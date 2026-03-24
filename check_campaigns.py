#!/usr/bin/env python3
"""Yandex Direct daily campaign report → Telegram."""

import json
import os
import ssl
import time
import urllib.request

API_URL = "https://api.direct.yandex.com/json/v5/reports"
YANDEX_TOKEN = os.environ["YANDEX_DIRECT_TOKEN"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def yandex_report(date_range, fields, report_type="CAMPAIGN_PERFORMANCE_REPORT"):
    """Fetch a report from Yandex Direct Reports API."""
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
        req = urllib.request.Request(API_URL, data=body, headers=headers)
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


def fmt_cost(val):
    """Format cost value with ₸ sign (KZT tenge)."""
    try:
        return f"{float(val):,.2f} ₸".replace(",", " ")
    except (ValueError, TypeError):
        return val


def escape_links(name):
    """Break auto-linking of domains in Telegram (e.g. author.today → author\u200b.today)."""
    import re
    return re.sub(r'\.(?=today|com|ru|net|org|io)', '.\u200b', name)


def fmt_ctr(val):
    """Format CTR as percentage."""
    try:
        return f"{float(val):.2f}%"
    except (ValueError, TypeError):
        return val


def build_daily_message(rows, period="Вчера"):
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
        f"Расход: <b>{fmt_cost(total_cost)}</b>",
        f"CTR: <b>{total_ctr:.2f}%</b>",
        f"Ср. цена клика: <b>{fmt_cost(avg_cpc)}</b>",
    ]

    if len(rows) > 1:
        lines += ["", "📋 <b>По кампаниям:</b>"]

    for r in sorted(rows, key=lambda x: float(x.get("Cost", 0)), reverse=True):
        cost = float(r.get("Cost", 0))
        clicks = int(r.get("Clicks", 0))
        impressions = int(r.get("Impressions", 0))
        if impressions == 0 and clicks == 0:
            continue
        name = escape_links(r.get("CampaignName", "—"))
        lines.append(
            f"\n▸ <b>{name}</b>\n"
            f"  {fmt_number(impressions)} показов · "
            f"{fmt_number(clicks)} кликов · "
            f"{fmt_cost(cost)}"
        )

    return "\n".join(lines)


def build_weekly_message(rows):
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
        f"Расход: <b>{fmt_cost(total_cost)}</b>",
        f"CTR: <b>{total_ctr:.2f}%</b>",
        f"Ср. цена клика: <b>{fmt_cost(avg_cpc)}</b>",
    ]

    # Aggregate by campaign
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
        name = escape_links(name)
        lines.append(
            f"\n▸ <b>{name}</b>\n"
            f"  {fmt_number(data['impressions'])} показов · "
            f"{fmt_number(data['clicks'])} кликов · "
            f"{fmt_cost(data['cost'])}"
        )

    return "\n".join(lines)


def main():
    report_type = os.environ.get("REPORT_TYPE", "daily")

    if os.environ.get("TEST_MODE") == "true":
        send_telegram(
            "🧪 <b>Тестовое уведомление</b>\n"
            "\n"
            "Мониторинг Яндекс Директ настроен.\n"
            "\n"
            "📊 <b>Пример сводки:</b>\n"
            "Показы: <b>1 234</b>\n"
            "Клики: <b>56</b>\n"
            "Расход: <b>789.00 ₸</b>\n"
            "CTR: <b>4.54%</b>"
        )
        print("Test notification sent.")
        return

    fields = ["CampaignName", "Impressions", "Clicks", "Cost", "Ctr", "AvgCpc"]

    if report_type == "weekly":
        date_range = "LAST_7_DAYS"
        tsv = yandex_report(date_range, fields)
        rows = parse_tsv(tsv, fields)
        msg = build_weekly_message(rows)
    elif report_type == "today":
        date_range = "TODAY"
        tsv = yandex_report(date_range, fields)
        rows = parse_tsv(tsv, fields)
        msg = build_daily_message(rows, period="Сегодня")
    else:
        date_range = "YESTERDAY"
        tsv = yandex_report(date_range, fields)
        rows = parse_tsv(tsv, fields)
        msg = build_daily_message(rows)

    send_telegram(msg)
    print(f"Report sent ({report_type}, {len(rows)} campaign rows)")


if __name__ == "__main__":
    main()
