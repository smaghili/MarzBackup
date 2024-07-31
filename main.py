import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters.command import Command
from config import API_TOKEN, ADMIN_CHAT_ID, load_config, save_config, get_db_name
from handlers import register_handlers
from backup import create_and_send_backup, get_db_container_name, get_db_password

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

async def validate_config():
    config = load_config()
    changes_made = False

    systems = ["marzban", "marzneshin"]
    for system in systems:
        try:
            # Validate and update db_container
            db_container = await get_db_container_name(system)
            if config.get(f"{system}_db_container") != db_container:
                config[f"{system}_db_container"] = db_container
                changes_made = True
                logging.info(f"Updated {system}_db_container to {db_container}")

            # Validate and update db_password
            db_password = get_db_password(system)
            if config.get(f"{system}_db_password") != db_password:
                config[f"{system}_db_password"] = db_password
                changes_made = True
                logging.info(f"Updated {system}_db_password")

            # Validate and update db_name
            db_name = get_db_name(system)
            if config.get(f"{system}_db_name") != db_name:
                config[f"{system}_db_name"] = db_name
                changes_made = True
                logging.info(f"Updated {system}_db_name to {db_name}")

        except Exception as e:
            logging.error(f"Error validating {system} config: {str(e)}")

    if changes_made:
        save_config(config)
        logging.info("Config file updated with corrected values")
    else:
        logging.info("Config file is up to date")

async def scheduled_backup():
    last_backup_time = 0
    last_interval_change_time = 0
    while True:
        config = load_config()
        interval = config.get("backup_interval_minutes", 0)
        interval_change_time = config.get("interval_change_time", 0)
        current_time = asyncio.get_event_loop().time()
        
        if interval > 0:
            if interval_change_time > last_interval_change_time:
                # Interval has changed, reset the timer
                last_backup_time = interval_change_time
                last_interval_change_time = interval_change_time
            
            time_since_last_backup = current_time - last_backup_time
            if time_since_last_backup >= interval * 60:
                success = await create_and_send_backup(bot)
                if success:
                    last_backup_time = current_time
            else:
                wait_time = (interval * 60) - time_since_last_backup
                await asyncio.sleep(min(wait_time, 60))
        else:
            await asyncio.sleep(60)  # Check every minute if interval is not set

async def on_startup(bot: Bot):
    await validate_config()
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text="ربات MarzBackup راه‌اندازی شد و تنظیمات بررسی شدند.")

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
