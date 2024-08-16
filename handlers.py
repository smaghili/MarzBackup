import os
import asyncio
import subprocess
import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Dispatcher
from aiogram.enums import ParseMode  # Import ParseMode from aiogram.enums
from config import save_config, load_config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define states
class BackupStates(StatesGroup):
    waiting_for_schedule = State()
    waiting_for_sql_file = State()

class ReportIntervalStates(StatesGroup):
    waiting_for_interval = State()

# Create a router instance
router = Router()

# Create a keyboard markup with the buttons
keyboard = types.ReplyKeyboardMarkup(
    keyboard=[
        [
            types.KeyboardButton(text="بازیابی بکاپ"),
            types.KeyboardButton(text="فاصله زمانی بکاپ"),
            types.KeyboardButton(text="بکاپ فوری")
        ],
        [
            types.KeyboardButton(text="تغییر زمان گزارش مصرف کاربران"),
            types.KeyboardButton(text="مشاهده مصرف کاربران")
        ]
    ],
    resize_keyboard=True
)

@router.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply("به ربات MarzBackup خوش آمدید! لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=keyboard)

@router.message(F.text == "بکاپ فوری")
async def handle_get_backup(message: types.Message):
    try:
        result = subprocess.run(['/bin/bash', '/opt/MarzBackup/backup.sh'], capture_output=True, text=True)
        if result.returncode == 0:
            await message.answer("پشتیبان‌گیری با موفقیت انجام شد و فایل ارسال گردید.")
        else:
            await message.answer(f"خطایی در فرآیند پشتیبان‌گیری رخ داد: {result.stderr}")
    except Exception as e:
        await message.answer(f"خطا در پشتیبان‌گیری: {e}")

@router.message(F.text == "فاصله زمانی بکاپ")
async def set_backup(message: types.Message, state: FSMContext):
    await state.set_state(BackupStates.waiting_for_schedule)
    await message.answer("لطفاً زمانبندی پشتیبان‌گیری را به صورت دقیقه ارسال کنید (مثال: '60' برای هر 60 دقیقه یکبار).")

def update_cron_job(interval):
    cron_schedule = f"*/{interval} * * * *"
    cron_command = f"/bin/bash /opt/MarzBackup/backup.sh"
    
    # Remove existing cron job
    subprocess.run("crontab -l | grep -v '/opt/MarzBackup/backup.sh' | crontab -", shell=True)
    
    # Add new cron job
    subprocess.run(f"(crontab -l ; echo '{cron_schedule} {cron_command}') | crontab -", shell=True)

@router.message(BackupStates.waiting_for_schedule)
async def process_schedule(message: types.Message, state: FSMContext):
    try:
        minutes = int(message.text)
        if minutes <= 0:
            raise ValueError("دقیقه باید عدد مثبت باشد")
        
        config = load_config()
        config["backup_interval_minutes"] = minutes
        save_config(config)
        
        # Update cron job
        update_cron_job(minutes)
        
        await message.answer(f"زمانبندی پشتیبان‌گیری به هر {minutes} دقیقه یکبار تنظیم شد.")
    except ValueError:
        await message.answer("لطفاً یک عدد صحیح مثبت برای دقیقه وارد کنید.")
    except Exception as e:
        await message.answer(f"خطا در پردازش زمانبندی: {e}")
    finally:
        await state.clear()

@router.message(F.text == "بازیابی بکاپ")
async def request_sql_file(message: types.Message, state: FSMContext):
    await state.set_state(BackupStates.waiting_for_sql_file)
    await message.answer("لطفاً فایل SQL پشتیبان را ارسال کنید.")

@router.message(BackupStates.waiting_for_sql_file)
async def process_sql_file(message: types.Message, state: FSMContext):
    if not message.document:
        await message.answer("لطفاً یک فایل ارسال کنید.")
        return
    
    if not message.document.file_name.lower().endswith('.sql'):
        await message.answer("فایل ارسالی معتبر نیست. لطفاً یک فایل با پسوند .sql ارسال کنید.")
        return

    try:
        config = load_config()
        system = "marzban" if os.path.exists("/opt/marzban") else "marzneshin"
        backup_dir = f"/var/lib/{system}/mysql/db-backup"

        # Create backup directory if it doesn't exist
        os.makedirs(backup_dir, exist_ok=True)

        # Download and save the file
        file = await message.bot.get_file(message.document.file_id)
        file_path = os.path.join(backup_dir, message.document.file_name)
        await message.bot.download_file(file.file_path, file_path)

        # Extract database information from config
        db_container = config.get("db_container")
        db_password = config.get("db_password")
        db_name = config.get("db_name")

        if not db_container or not db_password or not db_name:
            await message.answer("اطلاعات پایگاه داده در فایل کانفیگ یافت نشد.")
            return

        # Restore the database
        restore_command = f"docker exec -i {db_container} mariadb -u root -p{db_password} {db_name} < {file_path}"
        process = await asyncio.create_subprocess_shell(
            restore_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            await message.answer("بازیابی پایگاه داده با موفقیت انجام شد.")
        else:
            await message.answer(f"خطا در بازیابی پایگاه داده: {stderr.decode()}")

    except Exception as e:
        await message.answer(f"خطا در پردازش فایل SQL: {e}")
    finally:
        await state.clear()

@router.message(F.text == "تغییر زمان گزارش مصرف کاربران")
async def change_report_interval(message: types.Message, state: FSMContext):
    await state.set_state(ReportIntervalStates.waiting_for_interval)
    await message.answer("لطفا زمان گزارش مصرف کاربران را بر اساس دقیقه وارد کنید (توجه کنید مدت زمان‌های پایین باعث افزایش حجم پایگاه داده می‌شود. عدد پیشنهادی 60 است):")

@router.message(ReportIntervalStates.waiting_for_interval)
async def process_report_interval(message: types.Message, state: FSMContext):
    try:
        interval = int(message.text)
        if interval <= 0:
            raise ValueError("Interval must be positive")
        
        config = load_config()
        config['report_interval'] = interval
        save_config(config)
        
        # Restart hourlyReport.py
        process = await asyncio.create_subprocess_shell(
            "marzbackup restart user-usage",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            await message.answer(f"زمان گزارش مصرف کاربران به {interval} دقیقه تغییر یافت و سیستم گزارش‌گیری مجدداً راه‌اندازی شد.")
        else:
            await message.answer(f"خطا در تنظیم زمان گزارش: {stderr.decode()}")
    except ValueError:
        await message.answer("لطفاً یک عدد صحیح مثبت وارد کنید.")
    finally:
        await state.clear()

@router.message(F.text == "مشاهده مصرف کاربران")
async def show_user_usage(message: types.Message):
    logging.info("Starting show_user_usage function")
    try:
        result = subprocess.run(['node', '/root/table.js'], 
                                capture_output=True, 
                                text=True, 
                                check=True)
        
        logging.info("Table generation completed")
        
        # Add large emojis to make the output more prominent
        formatted_output = f"🔍 <b>User Usage Report</b> 🔍\n\n<pre>{result.stdout.strip()}</pre>"
        
        # Send the table as a message
        await message.answer(formatted_output, parse_mode=ParseMode.HTML)
    except subprocess.CalledProcessError as e:
        error_message = f"خطا در تولید جدول: {e.stderr}"
        logging.error(error_message)
        await message.answer(error_message)
    except Exception as e:
        error_message = f"خطایی رخ داد: {str(e)}"
        logging.exception("Exception in show_user_usage")
        await message.answer(error_message)

def register_handlers(dp: Dispatcher):
    dp.include_router(router)
