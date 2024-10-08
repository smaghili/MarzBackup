import os
import json
import subprocess
import asyncio
import signal
import re
import yaml
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        default_config = {"API_TOKEN": "", "ADMIN_CHAT_ID": "", "backup_interval_minutes": None, "db_password": None}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

config = load_config()
API_TOKEN = config.get("API_TOKEN")
ADMIN_CHAT_ID = config.get("ADMIN_CHAT_ID")
backup_interval_minutes = config.get("backup_interval_minutes")
db_password = config.get("db_password")

class BackupSettings(StatesGroup):
    waiting_for_schedule = State()

bot = None
dp = None
loop = None
backup_task = None

async def create_and_send_backup():
    try:
        result = subprocess.run(['/bin/bash', '/opt/MarzBackup/backup.sh'], capture_output=True, text=True)
        if result.returncode == 0:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text="پشتیبان‌گیری با موفقیت انجام شد.")
            return True
        else:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"خطایی در فرآیند پشتیبان‌گیری رخ داد: {result.stderr}")
            return False
    except Exception as e:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"خطایی در فرآیند پشتیبان‌گیری رخ داد: {str(e)}")
        return False

async def restore_backup(file: types.Document):
    global bot
    try:
        marzban_dir = subprocess.getoutput("find /opt /root -type d -iname 'marzban' -print -quit")
        marzneshin_dir = "/var/lib/marzneshin"

        if marzban_dir:
            system = "marzban"
            mysql_backup_dir = f"/var/lib/{system}/mysql/db-backup"
            database_name = "marzban"
        elif os.path.isdir(marzneshin_dir):
            system = "marzneshin"
            mysql_backup_dir = "/var/lib/marzneshin/mysql/db-backup"
            database_name = "marzneshin"
        else:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text="هیچ دایرکتوری Marzban یا Marzneshin یافت نشد.")
            return False

        os.makedirs(mysql_backup_dir, exist_ok=True)

        file_info = await bot.get_file(file.file_id)
        file_path = f"{mysql_backup_dir}/{file.file_name}"
        await bot.download_file(file_info.file_path, file_path)

        db_container = get_db_container_name(system)
        password = get_db_password(system)

        restore_command = f"docker exec -i {db_container} mariadb -u root -p\"{password}\" {database_name} < {file_path}"
        result = subprocess.run(restore_command, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Restore failed: {result.stderr}")

        print(f"{system.capitalize()} database restored successfully.")
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text="دیتابیس با موفقیت بازیابی شد.")
        return True
    except Exception as e:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"خطایی در فرآیند بازیابی رخ داد: {str(e)}")
        print(f"An error occurred during the restore process: {str(e)}")
        return False

async def schedule_backup(interval_minutes):
    while True:
        await create_and_send_backup()
        await asyncio.sleep(interval_minutes * 60)

async def initialize_bot():
    global API_TOKEN, ADMIN_CHAT_ID, bot, dp, loop, config, backup_interval_minutes, backup_task

    if not API_TOKEN:
        API_TOKEN = input("Please enter your bot token: ").strip()
        config["API_TOKEN"] = API_TOKEN
        save_config(config)

    if not ADMIN_CHAT_ID:
        ADMIN_CHAT_ID = input("Please enter the admin chat ID: ").strip()
        config["ADMIN_CHAT_ID"] = ADMIN_CHAT_ID
        save_config(config)

    bot = Bot(token=API_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    @dp.message(Command("start"))
    async def send_welcome(message: types.Message):
        if str(message.from_user.id) != ADMIN_CHAT_ID:
            await message.reply("شما مجاز به استفاده از این ربات نیستید.")
            return

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="تنظیم فاصله زمانی پشتیبان‌گیری")],
                [KeyboardButton(text="پشتیبان‌گیری فوری")],
                [KeyboardButton(text="بازیابی پشتیبان")]
            ],
            resize_keyboard=True
        )

        await message.reply("خوش آمدید! لطفاً یک گزینه را انتخاب کنید:", reply_markup=keyboard)

    @dp.message(lambda message: message.text == "پشتیبان‌گیری فوری")
    async def handle_get_backup(message: types.Message):
        if str(message.from_user.id) != ADMIN_CHAT_ID:
            await message.reply("شما مجاز به استفاده از این ربات نیستید.")
            return

        await message.reply("در حال شروع فرآیند پشتیبان‌گیری...")
        success = await create_and_send_backup()
        if success:
            await message.reply("پشتیبان‌گیری با موفقیت انجام و ارسال شد.")
        else:
            await message.reply("پشتیبان‌گیری با شکست مواجه شد. لطفاً لاگ‌ها را بررسی کنید.")

    @dp.message(lambda message: message.text == "تنظیم فاصله زمانی پشتیبان‌گیری")
    async def set_backup(message: types.Message, state: FSMContext):
        if str(message.from_user.id) != ADMIN_CHAT_ID:
            await message.reply("شما مجاز به استفاده از این ربات نیستید.")
            return

        await state.set_state(BackupSettings.waiting_for_schedule)
        await message.reply("لطفاً فاصله زمانی پشتیبان‌گیری را به دقیقه وارد کنید (مثلاً '60' برای هر ساعت):", reply_markup=ReplyKeyboardRemove())

    @dp.message(BackupSettings.waiting_for_schedule)
    async def process_schedule(message: types.Message, state: FSMContext):
        global backup_interval_minutes, backup_task
        try:
            interval_minutes = int(message.text)
            backup_interval_minutes = interval_minutes
            config["backup_interval_minutes"] = backup_interval_minutes
            save_config(config)

            if backup_task:
                backup_task.cancel()

            backup_task = asyncio.create_task(schedule_backup(interval_minutes))

            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="تنظیم فاصله زمانی پشتیبان‌گیری")],
                    [KeyboardButton(text="پشتیبان‌گیری فوری")],
                    [KeyboardButton(text="بازیابی پشتیبان")]
                ],
                resize_keyboard=True
            )

            await message.reply(f"زمان‌بندی پشتیبان‌گیری با موفقیت به هر {interval_minutes} دقیقه تنظیم شد.", reply_markup=keyboard)
            await state.clear()
        except ValueError:
            await message.reply("فرمت نامعتبر. لطفاً یک عدد به عنوان دقیقه وارد کنید.")

    @dp.message(lambda message: message.text == "بازیابی پشتیبان")
    async def handle_restore_backup(message: types.Message):
        if str(message.from_user.id) != ADMIN_CHAT_ID:
            await message.reply("شما مجاز به استفاده از این ربات نیستید.")
            return

        await message.reply("لطفاً فایل SQL را برای بازیابی ارسال کنید.")

    @dp.message(lambda message: message.document and message.document.file_name.endswith('.sql'))
    async def handle_document(message: types.Message):
        if str(message.from_user.id) != ADMIN_CHAT_ID:
            await message.reply("شما مجاز به استفاده از این ربات نیستید.")
            return

        document = message.document
        await message.reply("در حال بازیابی دیتابیس...")
        success = await restore_backup(document)
        if success:
            await message.reply("دیتابیس با موفقیت بازیابی شد.")
        else:
            await message.reply("بازیابی با شکست مواجه شد. لطفاً لاگ‌ها را بررسی کنید.")

    def shutdown_handler(signum, frame):
        print("Shutting down...")
        if backup_task:
            backup_task.cancel()
        loop.stop()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print("Bot is starting...")
    loop = asyncio.get_event_loop()
    if backup_interval_minutes:
        backup_task = asyncio.create_task(schedule_backup(backup_interval_minutes))

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(initialize_bot())
