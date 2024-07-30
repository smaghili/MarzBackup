import asyncio
import signal
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import API_TOKEN, ADMIN_CHAT_ID
from handlers import register_handlers

bot = None
dp = None

async def initialize_bot():
    global bot, dp
    try:
        bot = Bot(token=API_TOKEN)
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
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
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
