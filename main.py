import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import API_TOKEN, ADMIN_CHAT_ID
from handlers import handle_backup, handle_user_traffic_status

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Create a keyboard markup
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="پشتیبان‌گیری فوری")],
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

@dp.message(lambda message: message.text == "وضعیت مصرف کاربران")
async def traffic_status_command(message: types.Message):
    await handle_user_traffic_status(message)

async def main():
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text="ربات MarzBackup راه‌اندازی شد.", reply_markup=keyboard)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
