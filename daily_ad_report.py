import asyncio
import os
import re
import sys
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")

GRAPH_API = "https://graph.facebook.com/v21.0"

AD_ACCOUNTS = [
    {"id": "act_667014170402944", "name": "JANICE"},
    {"id": "act_282711469121395", "name": "TRAINER ADS (D9)"},
]

MSG_ACTION = "onsite_conversion.messaging_conversation_started_7d"


def get_action_value(actions: list, action_type: str) -> float:
    for a in (actions or []):
        if a.get("action_type") == action_type:
            return float(a.get("value", 0))
    return 0.0


def fetch_account_insights(account_id: str, date_preset: str) -> dict:
    url = f"{GRAPH_API}/{account_id}/insights"
    params = {
        "fields": "spend,impressions,clicks,actions,cost_per_action_type",
        "date_preset": date_preset,
        "access_token": META_ACCESS_TOKEN,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json().get("data", [])
        if data:
            d = data[0]
            spend = float(d.get("spend", 0) or 0)
            conversations = get_action_value(d.get("actions", []), MSG_ACTION)
            cpmc = get_action_value(d.get("cost_per_action_type", []), MSG_ACTION)
            return {
                "spend": spend,
                "impressions": int(d.get("impressions", 0) or 0),
                "clicks": int(d.get("clicks", 0) or 0),
                "conversations": int(conversations),
                "cpmc": cpmc,  # cost per messaging conversation
            }
    except Exception:
        pass
    return {"spend": 0, "impressions": 0, "clicks": 0, "conversations": 0, "cpmc": 0}


def fetch_top_low_cpmc_ads(account_id: str, date_preset: str, top_n: int = 5) -> list:
    url = f"{GRAPH_API}/{account_id}/ads"
    params = {
        "fields": f"name,insights.date_preset({date_preset}){{spend,impressions,clicks,actions,cost_per_action_type}}",
        "access_token": META_ACCESS_TOKEN,
        "limit": 200,
    }
    ads = []
    while url:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        ads.extend(data.get("data", []))
        next_url = data.get("paging", {}).get("next")
        url = next_url if next_url else None
        params = {}

    results = []
    for ad in ads:
        ins_data = ad.get("insights", {}).get("data", [])
        if not ins_data:
            continue
        ins = ins_data[0]
        spend = float(ins.get("spend", 0) or 0)
        conversations = get_action_value(ins.get("actions", []), MSG_ACTION)
        cpmc = get_action_value(ins.get("cost_per_action_type", []), MSG_ACTION)
        if spend <= 0 or conversations <= 0:
            continue
        results.append({
            "name": ad["name"],
            "spend": spend,
            "impressions": int(ins.get("impressions", 0) or 0),
            "clicks": int(ins.get("clicks", 0) or 0),
            "conversations": int(conversations),
            "cpmc": cpmc,
        })

    return sorted(results, key=lambda x: x["cpmc"])[:top_n]


def build_morning_report(accounts_data: list, top_ads: list, report_date: str) -> str:
    grand_spend = sum(d["spend"] for d in accounts_data)
    grand_impressions = sum(d["impressions"] for d in accounts_data)
    grand_clicks = sum(d["clicks"] for d in accounts_data)
    grand_conv = sum(d["conversations"] for d in accounts_data)
    grand_cpmc = grand_spend / grand_conv if grand_conv > 0 else 0

    lines = [
        f"📊 *广告日报 — {report_date}*",
        "",
        "━━━━━━━━━━━━━━━━━━",
        "*总览（所有账户）*",
        "",
        f"💰 总花费:       `MYR {grand_spend:,.2f}`",
        f"👁 总曝光:       `{grand_impressions:,}`",
        f"🖱 总点击:       `{grand_clicks:,}`",
        f"💬 总对话发起:   `{grand_conv}`",
        f"📉 平均对话费用: `MYR {grand_cpmc:.2f}`",
        "",
        "━━━━━━━━━━━━━━━━━━",
        "*各账户明细:*",
        "",
    ]

    for d in accounts_data:
        lines.append(
            f"📂 *{d['name']}*\n"
            f"  花费 `MYR {d['spend']:,.2f}` | 对话 `{d['conversations']}` | 单次对话 `MYR {d['cpmc']:.2f}`"
        )

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "*🏆 Top 5 最低单次对话费用广告:*",
        "",
    ]

    if top_ads:
        for i, ad in enumerate(top_ads, 1):
            name = ad["name"][:36] + "…" if len(ad["name"]) > 36 else ad["name"]
            lines.append(
                f"{i}. `MYR {ad['cpmc']:.2f}/对话` | {name}\n"
                f"   花费 `MYR {ad['spend']:,.2f}` | 对话 `{ad['conversations']}`"
            )
    else:
        lines.append("_暂无数据_")

    return "\n".join(lines)


async def fetch_account_data_async(account: dict, date_preset: str) -> tuple:
    loop = asyncio.get_event_loop()
    ins = await loop.run_in_executor(None, fetch_account_insights, account["id"], date_preset)
    top_ads = await loop.run_in_executor(None, fetch_top_low_cpmc_ads, account["id"], date_preset, 5)
    return {**ins, "name": account["name"]}, top_ads


async def send_morning_report():
    report_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    date_preset = "yesterday"
    print(f"拉取 {report_date} 的广告数据（并行）...")

    results = await asyncio.gather(*[
        fetch_account_data_async(account, date_preset) for account in AD_ACCOUNTS
    ])

    accounts_data = [r[0] for r in results]
    all_top_ads = [ad for r in results for ad in r[1]]
    top5 = sorted(all_top_ads, key=lambda x: x["cpmc"])[:5]

    report = build_morning_report(accounts_data, top5, report_date)
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode="Markdown")
    print(f"[{datetime.now().strftime('%H:%M')}] 早间报告已发送")


async def send_progress_report():
    date_preset = "today"
    report_date = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H:%M")
    print(f"拉取今日广告进度（并行）...")

    loop = asyncio.get_event_loop()
    results = await asyncio.gather(*[
        loop.run_in_executor(None, fetch_account_insights, account["id"], date_preset)
        for account in AD_ACCOUNTS
    ])
    accounts_data = [{**ins, "name": AD_ACCOUNTS[i]["name"]} for i, ins in enumerate(results)]

    grand_spend = sum(d["spend"] for d in accounts_data)
    grand_conv = sum(d["conversations"] for d in accounts_data)
    grand_cpmc = grand_spend / grand_conv if grand_conv > 0 else 0

    lines = [
        f"📈 *广告进度 — {report_date} {time_str}*",
        "",
        f"💰 总花费:       `MYR {grand_spend:,.2f}`",
        f"💬 总对话发起:   `{grand_conv}`",
        f"📉 平均对话费用: `MYR {grand_cpmc:.2f}`",
        "",
    ]
    for d in accounts_data:
        lines.append(
            f"📂 *{d['name']}*\n"
            f"  花费 `MYR {d['spend']:,.2f}` | 对话 `{d['conversations']}` | 单次对话 `MYR {d['cpmc']:.2f}`"
        )

    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="\n".join(lines), parse_mode="Markdown")
    print(f"[{datetime.now().strftime('%H:%M')}] 进度报告已发送")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    if mode == "morning":
        asyncio.run(send_morning_report())
    elif mode == "today":
        asyncio.run(send_progress_report())
    else:
        print("用法: python3 daily_ad_report.py [morning|today]")
        sys.exit(1)
