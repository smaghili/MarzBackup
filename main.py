import asyncio
import logging
import sys
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters.command import Command
from config import load_config, save_config, DB_NAME, DB_CONTAINER, DB_PASSWORD, DB_TYPE
from handlers import register_handlers
from backup import create_and_send_backup

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load config
config = load_config()
API_TOKEN = config.get('API_TOKEN')
ADMIN_CHAT_ID = config.get('ADMIN_CHAT_ID')

if not API_TOKEN or not ADMIN_CHAT_ID:
    logging.error("API_TOKEN or ADMIN_CHAT_ID is missing. Please run setup.py first.")
    sys.exit(1)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

async def schedule_backups():
    last_backup_time = datetime.now()
    while True:
        try:
            config = load_config()
            backup_interval = config.get('backup_interval_minutes', 60)  # Default to 60 minutes if not set
            interval_change_time = config.get('interval_change_time', 0)
            
            current_time = datetime.now()
            time_since_last_backup = (current_time - last_backup_time).total_seconds() / 60
            
            logging.info(f"Current time: {current_time}")
            logging.info(f"Last backup time: {last_backup_time}")
            logging.info(f"Time since last backup: {time_since_last_backup:.2f} minutes")
            logging.info(f"Backup interval: {backup_interval} minutes")
            
            if time_since_last_backup >= backup_interval:
                logging.info("Initiating backup...")
                success = await create_and_send_backup(bot)
                if success:
                    last_backup_time = current_time
                    logging.info("Backup completed successfully.")
                else:
                    logging.error("Backup failed.")
            
            # Calculate the time to wait until the next backup
            wait_time = max(0, (backup_interval - time_since_last_backup) * 60)
            logging.info(f"Waiting for {wait_time:.2f} seconds until next backup check.")
            
            await asyncio.sleep(wait_time)
        except Exception as e:
            logging.error(f"Error in backup scheduler: {e}")
            await asyncio.sleep(60)  # Wait for 1 minute before retrying

async def validate_config():
    config = load_config()
    changes_made = False

    try:
        # Validate and update db_container
        if config.get("db_container") != DB_CONTAINER:
            config["db_container"] = DB_CONTAINER
            changes_made = True
            logging.info(f"Updated db_container to {DB_CONTAINER}")

        # Validate and update db_password
        if config.get("db_password") != DB_PASSWORD:
            config["db_password"] = DB_PASSWORD
            changes_made = True
            logging.info("Updated db_password")

        # Validate and update db_name
        if config.get("db_name") != DB_NAME:
            config["db_name"] = DB_NAME
            changes_made = True
            logging.info(f"Updated db_name to {DB_NAME}")

        # Validate and update db_type
        if config.get("db_type") != DB_TYPE:
            config["db_type"] = DB_TYPE
            changes_made = True
            logging.info(f"Updated db_type to {DB_TYPE}")

        # Ensure report_interval exists in config
        if "report_interval" not in config:
            config["report_interval"] = 60  # Default to 60 minutes
            changes_made = True
            logging.info("Added default report_interval of 60 minutes")

    except Exception as e:
        logging.error(f"Error validating config: {str(e)}")

    if changes_made:
        save_config(config)
        logging.info("Config file updated with corrected values")
    else:
        logging.info("Config file is up to date")

async def on_startup(bot: Bot):
    await validate_config()
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text="MarzBackup bot has been successfully started!")
    asyncio.create_task(schedule_backups())

async def main():
    # Register all handlers
    register_handlers(dp)

    # Set up startup hook
    dp.startup.register(on_startup)

    # Start polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
