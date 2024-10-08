import logging
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters.command import Command
from config import load_config, save_config, DB_NAME, DB_CONTAINER, DB_PASSWORD, DB_TYPE
from handlers import register_handlers

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

async def main():
    # Register all handlers
    register_handlers(dp)

    # Set up startup hook
    dp.startup.register(on_startup)

    # Start polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
