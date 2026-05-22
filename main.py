"""
主程序 — 云端运行
使用 python-telegram-bot 内建 JobQueue 处理定时任务
"""
import logging
import os
from datetime import time
import pytz
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters

from bot_server import (
    ACCOUNT, DATE, REVENUE, ORDERS, NEW_CUSTOMERS, RETURNING_CUSTOMERS,
    get_account, get_date, get_revenue, get_orders,
    get_new_customers, get_returning_customers,
    cancel, help_cmd,
)
from daily_ad_report import send_morning_report, send_progress_report

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
KL = pytz.timezone("Asia/Kuala_Lumpur")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


async def job_morning(context):
    log.info("定时任务：早间报告（昨日）")
    await send_morning_report()


async def job_today(context):
    log.info(f"定时任务：今日进度")
    await send_progress_report()


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # ── 对话处理 ──────────────────────────────
    conv = ConversationHandler(
        entry_points=[CommandHandler("report", lambda u, c: __import__('bot_server').start_report(u, c))],
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

    # ── 定时任务（马来西亚时间）─────────────────
    jq = app.job_queue

    # 10:30am — 昨日完整报告
    jq.run_daily(job_morning, time=time(10, 30, tzinfo=KL))

    # 今日进度 — 12pm, 3pm, 4pm, 8pm, 10pm
    for hour in [12, 15, 16, 20, 22]:
        jq.run_daily(job_today, time=time(hour, 0, tzinfo=KL))

    # 测试 — 11:45pm
    jq.run_daily(job_today, time=time(23, 45, tzinfo=KL))

    log.info("✅ 所有定时任务已注册（马来西亚时间）")
    log.info("🚀 Bot 启动，等待消息...")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
