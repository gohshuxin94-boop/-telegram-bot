"""
主程序 — 云端运行
同时启动：
1. Telegram Bot（接收 /report 提交）
2. APScheduler（定时发送广告报告）
"""
import asyncio
import logging
import os
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from bot_server import main as start_bot
from daily_ad_report import send_morning_report, send_progress_report

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def run_async(coro):
    """在新事件循环中运行异步函数（供 scheduler 调用）"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


def job_morning():
    log.info("定时任务：早间报告（昨日）")
    run_async(send_morning_report())


def job_today():
    log.info(f"定时任务：今日进度 {datetime.now().strftime('%H:%M')}")
    run_async(send_progress_report())


def start_scheduler():
    scheduler = BackgroundScheduler(timezone="Asia/Kuala_Lumpur")

    # 每天 10:30am — 昨日完整报告
    scheduler.add_job(job_morning, CronTrigger(hour=10, minute=30))

    # 今日进度 — 12pm, 3pm, 4pm, 8pm, 10pm
    for hour in [12, 15, 16, 20, 22]:
        scheduler.add_job(job_today, CronTrigger(hour=hour, minute=0))

    # 测试 — 11:10pm（验证云端准时发送，之后可删除）
    scheduler.add_job(job_today, CronTrigger(hour=23, minute=10))

    scheduler.start()
    log.info("✅ Scheduler 已启动（马来西亚时间）")
    return scheduler


if __name__ == "__main__":
    log.info("🚀 启动中...")
    scheduler = start_scheduler()
    log.info("✅ 开始运行 Telegram Bot...")
    start_bot()  # 阻塞运行
