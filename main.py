import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters.command import Command
from config import API_TOKEN, ADMIN_CHAT_ID, load_config, save_config, DB_NAME, DB_CONTAINER, DB_PASSWORD, DB_TYPE, get_or_ask
from handlers import register_handlers
from backup import create_and_send_backup

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = None
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

async def init_bot():
    global bot
    global API_TOKEN
    global ADMIN_CHAT_ID
    
    while True:
        try:
            bot = Bot(token=API_TOKEN)
            await bot.get_me()
            break
        except Exception as e:
            logging.error(f"Invalid bot token: {e}")
            API_TOKEN = get_or_ask('API_TOKEN', "Please enter your Telegram bot token: ")
    
    # Validate ADMIN_CHAT_ID
    while True:
        try:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text="Validating admin chat ID...")
            break
        except Exception as e:
            logging.error(f"Invalid admin chat ID: {e}")
            ADMIN_CHAT_ID = get_or_ask('ADMIN_CHAT_ID', "Please enter the admin chat ID: ")

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
    await init_bot()
    
    # Register all handlers
    register_handlers(dp)

    # Set up startup hook
    dp.startup.register(on_startup)

    # Start polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
