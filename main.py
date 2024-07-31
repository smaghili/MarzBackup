import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import API_TOKEN, ADMIN_CHAT_ID, load_config, save_config
from handlers import handle_backup, handle_user_traffic_status, set_backup, process_schedule
from backup import create_and_send_backup

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Create a keyboard markup
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="پشتیبان‌گیری فوری")],
        [KeyboardButton(text="تنظیم فاصله زمانی پشتیبان‌گیری")],
        [KeyboardButton(text="وضعیت مصرف کاربران")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply("به ربات MarzBackup خوش آمدید! لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=keyboard)

@dp.message(lambda message: message.text == "پشتیبان‌گیری فوری")
async def backup_command(message: types.Message):
    await handle_backup(bot)

@dp.message(lambda message: message.text == "تنظیم فاصله زمانی پشتیبان‌گیری")
async def set_backup_command(message: types.Message):
    await set_backup(message, dp.current_state())

@dp.message(lambda message: message.text == "وضعیت مصرف کاربران")
async def traffic_status_command(message: types.Message):
    await handle_user_traffic_status(message)

async def scheduled_backup():
    config = load_config()
    interval = config.get("backup_interval_minutes", 0)
    if interval > 0:
        while True:
            await asyncio.sleep(interval * 60)
            await create_and_send_backup(bot)

async def main():
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text="ربات MarzBackup راه‌اندازی شد.", reply_markup=keyboard)
    asyncio.create_task(scheduled_backup())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
