import os
import asyncio
import subprocess
import yaml
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Dispatcher
from config import save_config, load_config
from backup import handle_backup, create_and_send_backup

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
    try:
        success = await handle_backup(message.bot)
        if success:
            await message.answer("پشتیبان‌گیری با موفقیت انجام شد و فایل ارسال گردید.")
        else:
            await message.answer("خطایی در فرآیند پشتیبان‌گیری رخ داد.")
    except Exception as e:
        await message.answer(f"خطا در پشتیبان‌گیری: {e}")

@router.message(F.text == "تنظیم فاصله زمانی پشتیبان‌گیری")
async def set_backup(message: types.Message, state: FSMContext):
    await state.set_state(BackupStates.waiting_for_schedule)
    await message.answer("لطفاً زمانبندی پشتیبان‌گیری را به صورت دقیقه ارسال کنید (مثال: '60' برای هر 60 دقیقه یکبار).")

@router.message(BackupStates.waiting_for_schedule)
async def process_schedule(message: types.Message, state: FSMContext):
    try:
        minutes = int(message.text)
        if minutes <= 0:
            raise ValueError("دقیقه باید عدد مثبت باشد")
        
        config = load_config()
        config["backup_interval_minutes"] = minutes
        config["interval_change_time"] = asyncio.get_event_loop().time()
        save_config(config)
        
        await state.clear()
        await message.answer(f"زمانبندی پشتیبان‌گیری به هر {minutes} دقیقه یکبار تنظیم شد.")
        
        # Perform an immediate backup
        success = await create_and_send_backup(message.bot)
        if success:
            await message.answer("پشتیبان‌گیری فوری با موفقیت انجام شد و فایل ارسال گردید.")
        else:
            await message.answer("خطایی در فرآیند پشتیبان‌گیری فوری رخ داد.")
    except ValueError:
        await message.answer("لطفاً یک عدد صحیح مثبت برای دقیقه وارد کنید.")
    except Exception as e:
        await message.answer(f"خطا در پردازش زمانبندی: {e}")
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
        container_name = config.get("db_container")
        db_password = config.get("db_password")
        db_name = config.get("db_name")

        if not container_name or not db_password or not db_name:
            await message.answer("اطلاعات پایگاه داده در فایل کانفیگ یافت نشد.")
            return

        # Restore the database
        restore_command = f"docker exec -i {container_name} mariadb -u root -p{db_password} {db_name} < {file_path}"
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
        
        await state.clear()
        await message.answer(f"زمان گزارش مصرف کاربران به {interval} دقیقه تغییر یافت.")
    except ValueError:
        await message.answer("لطفاً یک عدد صحیح مثبت وارد کنید.")

def register_handlers(dp: Dispatcher):
    dp.include_router(router)
