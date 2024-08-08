import os
import asyncio
import subprocess
import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Dispatcher
from config import save_config, load_config

# Define states
class BackupStates(StatesGroup):
    waiting_for_schedule = State()
    waiting_for_sql_file = State()

class ReportIntervalStates(StatesGroup):
    waiting_for_interval = State()

# Create a router instance
router = Router()

# Create a keyboard markup
keyboard = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="پشتیبان‌گیری فوری")],
        [types.KeyboardButton(text="تنظیم فاصله زمانی پشتیبان‌گیری")],
        [types.KeyboardButton(text="بازیابی پشتیبان")],
        [types.KeyboardButton(text="تغییر زمان گزارش مصرف کاربران")]
    ],
    resize_keyboard=True
)

@router.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply("به ربات MarzBackup خوش آمدید! لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=keyboard)

@router.message(F.text == "پشتیبان‌گیری فوری")
async def handle_get_backup(message: types.Message):
    await message.answer("در حال تهیه پشتیبان... لطفاً صبر کنید.")
    try:
        process = await asyncio.create_subprocess_shell(
            "/usr/bin/python3 /opt/MarzBackup/backup.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        logging.info(f"Backup process returned: stdout={stdout.decode().strip()}, stderr={stderr.decode().strip()}")
        
        if process.returncode == 0:
            # Extract the backup file path
            for line in stdout.decode().strip().split('\n'):
                if line.startswith("BACKUP_PATH:"):
                    backup_file_path = line.split(":", 1)[1].strip()
                    break
            else:
                raise ValueError("Backup path not found in output")

            logging.info(f"Extracted backup file path: {backup_file_path}")
            
            if os.path.exists(backup_file_path):
                file_size = os.path.getsize(backup_file_path)
                logging.info(f"Backup file exists. Size: {file_size} bytes")
                
                try:
                    await message.answer_document(
                        types.FSInputFile(backup_file_path),
                        caption="فایل پشتیبان با موفقیت ایجاد و ارسال شد."
                    )
                    logging.info("Document sent successfully")
                except Exception as send_error:
                    logging.error(f"Error sending document: {str(send_error)}")
                    await message.answer(f"خطا در ارسال فایل: {str(send_error)}")
            else:
                await message.answer(f"فایل پشتیبان در مسیر {backup_file_path} یافت نشد.")
                logging.error(f"Backup file not found: {backup_file_path}")
        else:
            error_message = stderr.decode().strip()
            await message.answer(f"خطا در ایجاد پشتیبان: {error_message}")
            logging.error(f"Backup creation failed: {error_message}")
    
    except Exception as e:
        logging.error(f"Error in backup process: {str(e)}")
        await message.answer("خطایی در فرآیند پشتیبان‌گیری رخ داد. لطفاً لاگ‌ها را بررسی کنید.")

@router.message(F.text == "تنظیم فاصله زمانی پشتیبان‌گیری")
async def set_backup(message: types.Message, state: FSMContext):
    await state.set_state(BackupStates.waiting_for_schedule)
    await message.answer("لطفاً زمانبندی پشتیبان‌گیری را به صورت دقیقه ارسال کنید (مثال: '10' برای هر 10 دقیقه یکبار).")

@router.message(BackupStates.waiting_for_schedule)
async def process_schedule(message: types.Message, state: FSMContext):
    try:
        minutes = int(message.text)
        if minutes <= 0:
            raise ValueError("دقیقه باید عدد مثبت باشد")
        
        config = load_config()
        config["backup_interval_minutes"] = minutes
        save_config(config)
        
        # Run the update_backup_cron command automatically after setting the interval
        update_backup_cron_command = "marzbackup update_backup_interval"
        process = await asyncio.create_subprocess_shell(
            update_backup_cron_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            await message.answer(f"زمانبندی پشتیبان‌گیری به هر {minutes} دقیقه یکبار تنظیم شد.")
        else:
            await message.answer(f"خطا در تنظیم زمانبندی: {stderr.decode()}")
    except ValueError:
        await message.answer("لطفاً یک عدد صحیح مثبت برای دقیقه وارد کنید.")
    finally:
        await state.clear()

@router.message(F.text == "بازیابی پشتیبان")
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

def register_handlers(dp: Dispatcher):
    dp.include_router(router)
