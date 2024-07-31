import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import API_TOKEN, ADMIN_CHAT_ID
from handlers import register_handlers
from backup import create_and_send_backup

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

async def scheduled_backup():
    # ... (بقیه کد بدون تغییر)

async def on_startup(bot: Bot):
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text="ربات MarzBackup راه‌اندازی شد.")

async def main():
    # Register all handlers
    register_handlers(dp)

    # Set up startup hook
    dp.startup.register(on_startup)

    # Start scheduled backup task
    asyncio.create_task(scheduled_backup())

    # Start polling
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
