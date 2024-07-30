
import asyncio
import signal
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import load_config, save_config
from handlers import register_handlers

config = load_config()
API_TOKEN = config.get("API_TOKEN")
ADMIN_CHAT_ID = config.get("ADMIN_CHAT_ID")
backup_interval_minutes = config.get("backup_interval_minutes")
backup_task = None

bot = None
dp = None

async def initialize_bot():
    global API_TOKEN, ADMIN_CHAT_ID, bot, dp, config, backup_interval_minutes, backup_task
    try:
        if not API_TOKEN:
            API_TOKEN = input("Please enter your bot token: ").strip()
            config["API_TOKEN"] = API_TOKEN
            save_config(config)
        if not ADMIN_CHAT_ID:
            ADMIN_CHAT_ID = input("Please enter the admin chat ID: ").strip()
            config["ADMIN_CHAT_ID"] = ADMIN_CHAT_ID
            save_config(config)
        bot = Bot(token=API_TOKEN)
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)  # Updated for aiogram 3.x
        dp.set_bot(bot)  # Set the bot
    except Exception as e:
        raise RuntimeError(f"Failed to initialize bot: {e}")

def shutdown_handler(signum, frame):
    print("Shutting down...")
    asyncio.get_event_loop().stop()

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

async def main():
    await initialize_bot()
    register_handlers(dp)
    print("Bot is starting...")
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
