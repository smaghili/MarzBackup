import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import load_config, save_config
from handlers import register_handlers
import fcntl

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

def acquire_lock():
    try:
        lock_file = open("/tmp/marzbackup_bot.lock", "w")
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except IOError:
        print("Another instance is already running")
        sys.exit(1)

lock_file = acquire_lock()

async def validate_config():
    config = load_config()
    changes_made = False

    try:
        # Validate and update db_container
        if config.get("db_container") != config.get("db_container"):
            config["db_container"] = config.get("db_container")
            changes_made = True
            logging.info(f"Updated db_container to {config.get('db_container')}")

        # Validate and update db_password
        if config.get("db_password") != config.get("db_password"):
            config["db_password"] = config.get("db_password")
            changes_made = True
            logging.info("Updated db_password")

        # Validate and update db_name
        if config.get("db_name") != config.get("db_name"):
            config["db_name"] = config.get("db_name")
            changes_made = True
            logging.info(f"Updated db_name to {config.get('db_name')}")

        # Validate and update db_type
        if config.get("db_type") != config.get("db_type"):
            config["db_type"] = config.get("db_type")
            changes_made = True
            logging.info(f"Updated db_type to {config.get('db_type')}")

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

async def send_telegram_message(message):
    try:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")

async def on_startup(bot: Bot):
    await validate_config()
    await send_telegram_message("ربات MarzBackup با موفقیت راه‌اندازی شد!")

async def main():
    # Register all handlers
    register_handlers(dp)

    # Set up startup hook
    dp.startup.register(on_startup)

    # Start polling
    await dp.start_polling(bot, timeout=60)

if __name__ == '__main__':
    asyncio.run(main())
