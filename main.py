import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters.command import Command
from config import API_TOKEN, ADMIN_CHAT_ID, load_config
from handlers import register_handlers
from backup import create_and_send_backup

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

async def scheduled_backup():
    last_backup_time = 0
    while True:
        config = load_config()
        interval = config.get("backup_interval_minutes", 0)
        current_time = asyncio.get_event_loop().time()
        
        if interval > 0:
            time_since_last_backup = current_time - last_backup_time
            if time_since_last_backup >= interval * 60:
                await create_and_send_backup(bot)
                last_backup_time = current_time
            else:
                wait_time = (interval * 60) - time_since_last_backup
                await asyncio.sleep(min(wait_time, 60))
        else:
            await asyncio.sleep(60)  # Check every minute if interval is not set

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
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
