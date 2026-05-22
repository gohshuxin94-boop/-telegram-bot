import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


async def send_message(text: str, chat_id: str = None):
    bot = Bot(token=BOT_TOKEN)
    target = chat_id or CHAT_ID
    await bot.send_message(chat_id=target, text=text)
    print(f"已发送: {text}")


async def send_photo(image_path: str, caption: str = None, chat_id: str = None):
    bot = Bot(token=BOT_TOKEN)
    target = chat_id or CHAT_ID
    with open(image_path, "rb") as f:
        await bot.send_photo(chat_id=target, photo=f, caption=caption)
    print(f"已发送图片: {image_path}")


if __name__ == "__main__":
    asyncio.run(send_message("Hello from my Bot! 🎉"))
