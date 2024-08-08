import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import load_config, save_config, API_TOKEN, ADMIN_CHAT_ID
from handlers import register_handlers, send_startup_message
import fcntl

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

LOCK_FILE = "/tmp/marzbackup_bot.lock"

def acquire_lock():
    try:
        lock_fd = open(LOCK_FILE, 'w')
        fcntl.lockf(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except (IOError, OSError):
        logging.error("Another instance is already running")
        sys.exit(1)

def release_lock(lock_fd):
    try:
        fcntl.lockf(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        os.remove(LOCK_FILE)
    except (IOError, OSError) as e:
        logging.error(f"Error releasing lock: {e}")

lock_fd = acquire_lock()

async def validate_config():
    config = load_config()
    # Add any config validation logic here if needed
    save_config(config)

async def on_startup(bot: Bot):
    await validate_config()
    operation_type = sys.argv[1] if len(sys.argv) > 1 else "start"
    await send_startup_message(bot, operation_type)

async def main():
    try:
        # Register all handlers
        register_handlers(dp)

        # Set up startup hook
        dp.startup.register(on_startup)

        # Start polling
        await dp.start_polling(bot, timeout=60)
    finally:
        release_lock(lock_fd)

if __name__ == '__main__':
    asyncio.run(main())
