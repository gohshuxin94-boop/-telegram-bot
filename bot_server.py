import asyncio
import os
import re
import requests
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("CHAT_ID"))
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")

AD_ACCOUNTS = [
    {"id": "act_667014170402944", "name": "JANICE"},
    {"id": "act_282711469121395", "name": "TRAINER ADS (D9)"},
]

ACCOUNT, DATE, REVENUE, ORDERS, NEW_CUSTOMERS, RETURNING_CUSTOMERS = range(6)

ACCOUNT_NAMES = [a["name"] for a in AD_ACCOUNTS]


def fetch_single_account(account_id: str, date_preset: str) -> dict:
    url = f"https://graph.facebook.com/v21.0/{account_id}/insights"
    params = {
        "fields": "spend,clicks,impressions",
        "date_preset": date_preset,
        "access_token": META_ACCESS_TOKEN,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json().get("data", [])
        if data:
            return {
                "spend": float(data[0].get("spend", 0) or 0),
                "clicks": int(data[0].get("clicks", 0) or 0),
                "impressions": int(data[0].get("impressions", 0) or 0),
            }
    except Exception:
        pass
    return {"spend": 0, "clicks": 0, "impressions": 0}


async def fetch_ad_data(account_id: str, report_date: str) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    date_preset = "today" if report_date == today else "yesterday"
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fetch_single_account, account_id, date_preset)


def parse_number(text: str) -> Optional[float]:
    cleaned = re.sub(r"[^\d.]", "", text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return None


async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    keyboard = [[name] for name in ACCOUNT_NAMES]
    await update.message.reply_text(
        "📋 *销售报告提交*\n\n请选择 *广告账户*：",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return ACCOUNT


async def get_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    matched = next((a for a in AD_ACCOUNTS if a["name"].upper() == text.upper()), None)
    if not matched:
        keyboard = [[name] for name in ACCOUNT_NAMES]
        await update.message.reply_text(
            "请从选项中选择账户：",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return ACCOUNT
    context.user_data["account"] = matched
    today = datetime.now().strftime("%Y-%m-%d")
    await update.message.reply_text(
        f"✅ 账户：*{matched['name']}*\n\n请输入 *报告日期*\n直接发 `今天` 则使用今天 ({today})",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return DATE


async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text in ("今天", "today"):
        context.user_data["report_date"] = datetime.now().strftime("%Y-%m-%d")
    else:
        cleaned = re.sub(r"[/.]", "-", text)
        try:
            datetime.strptime(cleaned, "%Y-%m-%d")
            context.user_data["report_date"] = cleaned
        except ValueError:
            try:
                dt = datetime.strptime(cleaned, "%d-%m-%Y")
                context.user_data["report_date"] = dt.strftime("%Y-%m-%d")
            except ValueError:
                await update.message.reply_text(
                    "格式不对，请输入日期如：`2026-05-22` 或发 `今天`",
                    parse_mode="Markdown",
                )
                return DATE
    await update.message.reply_text(
        f"✅ 日期：`{context.user_data['report_date']}`\n\n*销售额* 是多少？（单位 MYR）",
        parse_mode="Markdown",
    )
    return REVENUE


async def get_revenue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    val = parse_number(update.message.text)
    if val is None or val < 0:
        await update.message.reply_text("请输入有效数字，例如：5000")
        return REVENUE
    context.user_data["revenue"] = val
    await update.message.reply_text("*订单数量* 是多少？", parse_mode="Markdown")
    return ORDERS


async def get_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    val = parse_number(update.message.text)
    if val is None or val < 0:
        await update.message.reply_text("请输入有效数字，例如：25")
        return ORDERS
    context.user_data["orders"] = int(val)
    await update.message.reply_text("*新顾客成交数量* 是多少？", parse_mode="Markdown")
    return NEW_CUSTOMERS


async def get_new_customers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    val = parse_number(update.message.text)
    if val is None or val < 0:
        await update.message.reply_text("请输入有效数字，例如：10")
        return NEW_CUSTOMERS
    context.user_data["new_customers"] = int(val)
    await update.message.reply_text("*旧顾客成交数量* 是多少？", parse_mode="Markdown")
    return RETURNING_CUSTOMERS


async def get_returning_customers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    val = parse_number(update.message.text)
    if val is None or val < 0:
        await update.message.reply_text("请输入有效数字，例如：15")
        return RETURNING_CUSTOMERS
    context.user_data["returning_customers"] = int(val)

    account = context.user_data["account"]
    report_date = context.user_data.get("report_date", datetime.now().strftime("%Y-%m-%d"))

    await update.message.reply_text("⏳ 正在计算中，请稍候...")

    ad = await fetch_ad_data(account["id"], report_date)
    revenue = context.user_data["revenue"]
    orders = context.user_data["orders"]
    new_cust = context.user_data["new_customers"]
    ret_cust = context.user_data["returning_customers"]
    total_cust = new_cust + ret_cust
    spend = ad["spend"]
    clicks = ad["clicks"]

    roas = revenue / spend if spend > 0 else 0
    avg_order = revenue / orders if orders > 0 else 0
    new_cust_pct = (new_cust / total_cust * 100) if total_cust > 0 else 0
    total_conv_rate = (orders / clicks * 100) if clicks > 0 else 0
    new_cust_conv_rate = (new_cust / clicks * 100) if clicks > 0 else 0

    submitter = update.effective_user.first_name or "未知"
    submit_time = datetime.now().strftime("%H:%M")

    report = (
        f"🧾 *销售日报 — {report_date}*\n"
        f"_账户: {account['name']} | {submit_time} | {submitter}_\n\n"
        f"💰 销售额:        `MYR {revenue:,.2f}`\n"
        f"📦 订单数:        `{orders}`\n"
        f"🆕 新顾客:        `{new_cust}` ({new_cust_pct:.0f}%)\n"
        f"🔄 旧顾客:        `{ret_cust}` ({100 - new_cust_pct:.0f}%)\n"
        f"🧑 总成交:        `{total_cust}`\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 *自动计算*\n\n"
        f"📈 ROAS:                  `{roas:.2f}x`\n"
        f"🛍 平均客单价:            `MYR {avg_order:,.2f}`\n"
        f"📊 Total Conv Rate:       `{total_conv_rate:.2f}%`\n"
        f"🆕 New Cust Conv Rate:    `{new_cust_conv_rate:.2f}%`\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📣 *广告数据（{report_date}）*\n\n"
        f"💸 广告花费: `MYR {spend:,.2f}`\n"
        f"🖱 广告点击: `{clicks:,}`\n"
        f"👁 广告曝光: `{ad['impressions']:,}`"
    )

    await update.message.reply_text(report, parse_mode="Markdown")

    if update.effective_chat.id != ADMIN_CHAT_ID:
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=report, parse_mode="Markdown")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("已取消。发送 /report 重新开始。", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 *可用指令*\n\n"
        "/report — 提交销售报告\n"
        "/cancel — 取消当前操作",
        parse_mode="Markdown",
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("report", start_report)],
        states={
            ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_account)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            REVENUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_revenue)],
            ORDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_orders)],
            NEW_CUSTOMERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_customers)],
            RETURNING_CUSTOMERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_returning_customers)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("start", help_cmd))

    print(f"[{datetime.now().strftime('%H:%M')}] Bot 已启动，等待消息...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
