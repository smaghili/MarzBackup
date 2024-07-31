from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import save_config, load_config
from backup import handle_backup, create_and_send_backup

# Define states
class BackupStates(StatesGroup):
    waiting_for_schedule = State()

# Create a router instance
router = Router()

# Create a keyboard markup
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="پشتیبان‌گیری فوری")],
        [KeyboardButton(text="تنظیم فاصله زمانی پشتیبان‌گیری")]
    ],
    resize_keyboard=True
)

@router.message(Command("start"))
async def send_welcome(message: Message):
    await message.reply("به ربات MarzBackup خوش آمدید! لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=keyboard)

@router.message(F.text == "پشتیبان‌گیری فوری")
async def handle_get_backup(message: Message):
    try:
        success = await handle_backup(message.bot)
        if success:
            await message.answer("پشتیبان‌گیری با موفقیت انجام شد و فایل ارسال گردید.")
        else:
            await message.answer("خطایی در فرآیند پشتیبان‌گیری رخ داد.")
    except Exception as e:
        await message.answer(f"خطا در پشتیبان‌گیری: {e}")

@router.message(F.text == "تنظیم فاصله زمانی پشتیبان‌گیری")
async def set_backup(message: Message, state: FSMContext):
    await state.set_state(BackupStates.waiting_for_schedule)
    await message.answer("لطفاً زمانبندی پشتیبان‌گیری را به صورت دقیقه ارسال کنید (مثال: '60' برای هر 60 دقیقه یکبار).")

@router.message(BackupStates.waiting_for_schedule)
async def process_schedule(message: Message, state: FSMContext):
    try:
        minutes = int(message.text)
        if minutes <= 0:
            raise ValueError("دقیقه باید عدد مثبت باشد")
        
        config = load_config()
        config["backup_interval_minutes"] = minutes
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

def register_handlers(dp: Dispatcher):
    dp.include_router(router)
