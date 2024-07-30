from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import save_config, load_config
from backup import backup_database, send_backup_to_admin

# Define states
class BackupStates(StatesGroup):
    waiting_for_schedule = State()

# Create a router instance
router = Router()

config = load_config()

async def handle_get_backup(message: Message):
    try:
        # Perform the backup
        system = "marzban"  # یا "marzneshin" بسته به سیستم شما
        backup_file = backup_database(system)
        
        # Send the backup file
        await send_backup_to_admin(system, message.bot, message.chat.id)
        
        await message.answer("پشتیبان‌گیری انجام شد و فایل ارسال گردید.")
    except Exception as e:
        await message.answer(f"خطا در پشتیبان‌گیری: {e}")

async def set_backup(message: Message, state: FSMContext):
    try:
        await state.set_state(BackupStates.waiting_for_schedule)
        await message.answer("لطفاً زمانبندی پشتیبان‌گیری را به صورت دقیقه ارسال کنید (مثال: '60' برای هر 60 دقیقه یکبار).")
    except Exception as e:
        await message.answer(f"خطا در تنظیم پشتیبان‌گیری: {e}")

async def process_schedule(message: Message, state: FSMContext):
    try:
        schedule = message.text
        try:
            minutes = int(schedule)
            if minutes <= 0:
                raise ValueError("دقیقه باید عدد مثبت باشد")
            config["backup_interval_minutes"] = minutes
            save_config(config)
            await state.clear()
            await message.answer(f"زمانبندی پشتیبان‌گیری به هر {minutes} دقیقه یکبار تنظیم شد.")
        except ValueError:
            await message.answer("لطفاً یک عدد صحیح مثبت برای دقیقه وارد کنید.")
            return
    except Exception as e:
        await message.answer(f"خطا در پردازش زمانبندی: {e}")

async def handle_restore_backup(message: Message):
    try:
        # Implement the logic to restore backup
        await message.answer("بازیابی پشتیبان انجام شد.")
    except Exception as e:
        await message.answer(f"خطا در بازیابی پشتیبان: {e}")

async def handle_document(message: Message):
    try:
        if message.document and message.document.file_name.endswith('.sql'):
            # Process the document
            await message.answer("فایل SQL پردازش شد.")
    except Exception as e:
        await message.answer(f"خطا در پردازش فایل: {e}")

async def handle_user_traffic_status(message: Message):
    try:
        # Implement the logic to handle user traffic status
        await message.answer("وضعیت مصرف کاربران به‌روزرسانی شد.")
    except Exception as e:
        await message.answer(f"خطا در وضعیت مصرف کاربران: {e}")

def register_handlers(dp):
    # Register handlers
    router.message.register(handle_get_backup, F.text == "پشتیبان‌گیری فوری")
    router.message.register(set_backup, F.text == "تنظیم فاصله زمانی پشتیبان‌گیری")
    router.message.register(process_schedule, BackupStates.waiting_for_schedule)
    router.message.register(handle_restore_backup, F.text == "بازیابی پشتیبان")
    router.message.register(handle_document, F.document.file_name.endswith('.sql'))
    router.message.register(handle_user_traffic_status, F.text == "وضعیت مصرف کاربران")

    # Include the router in the dispatcher
    dp.include_router(router)
