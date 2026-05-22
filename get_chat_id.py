"""
运行此脚本获取你的 Chat ID。
步骤：先给你的 Bot 发一条消息，再运行此脚本。
"""
import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def main():
    bot = Bot(token=BOT_TOKEN)
    updates = await bot.get_updates()
    if not updates:
        print("没有收到消息，请先在 Telegram 中给你的 Bot 发一条消息，再运行此脚本。")
        return
    for update in updates:
        chat = update.message.chat
        print(f"Chat ID : {chat.id}")
        print(f"用户名  : {chat.username or '(无)'}")
        print(f"姓名    : {chat.first_name} {chat.last_name or ''}")


asyncio.run(main())
