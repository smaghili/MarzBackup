from aiogram import Dispatcher, types
from aiogram.client import bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from config import load_config, save_config
from backup import create_and_send_backup, restore_backup

config = load_config()


async def send_welcome(message: types.Message):
    if str(message.from_user.id) not in config["admins"] and str(message.from_user.id) != config["ADMIN_CHAT_ID"]:
        await message.reply("شما مجاز به استفاده از این ربات نیستید.")
        return
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="تنظیم فاصله زمانی پشتیبان‌گیری")],
            [KeyboardButton(text="پشتیبان‌گیری فوری")],
            [KeyboardButton(text="بازیابی پشتیبان")],
            [KeyboardButton(text="افزودن ادمین")],
            [KeyboardButton(text="وضعیت مصرف کاربران")]
        ],
        resize_keyboard=True
    )
    await message.reply("خوش آمدید! لطفاً یک گزینه را انتخاب کنید:", reply_markup=keyboard)


async def add_admin(message: types.Message, state: FSMContext):
    if str(message.from_user.id) != config["ADMIN_CHAT_ID"]:
        await message.reply("شما مجاز به استفاده از این ربات نیستید.")
        return
    await state.set_state(State("waiting_for_new_admin"))
    await message.reply("لطفاً شناسه عددی ادمین جدید را وارد کنید:")


async def process_new_admin(message: types.Message, state: FSMContext):
    new_admin_id = message.text.strip()
    if new_admin_id.isdigit():
        config["admins"].append(new_admin_id)
        save_config(config)
        await message.reply(f"ادمین جدید با شناسه {new_admin_id} با موفقیت اضافه شد.")
        await state.clear()
    else:
        await message.reply("لطفاً یک شناسه عددی معتبر وارد کنید.")


async def handle_get_backup(message: types.Message):
    if str(message.from_user.id) not in config["admins"] and str(message.from_user.id) != config["ADMIN_CHAT_ID"]:
        await message.reply("شما مجاز به استفاده از این ربات نیستید.")
        return
    await message.reply("در حال شروع فرآیند پشتیبان‌گیری...")
    success = await create_and_send_backup()
    if success:
        await message.reply("پشتیبان‌گیری با موفقیت انجام و ارسال شد.")
    else:
        await message.reply("پشتیبان‌گیری با شکست مواجه شد. لطفاً لاگ‌ها را بررسی کنید.")


async def set_backup(message: types.Message, state: FSMContext):
    if str(message.from_user.id) not in config["admins"] and str(message.from_user.id) != config["ADMIN_CHAT_ID"]:
        await message.reply("شما مجاز به استفاده از این ربات نیستید.")
        return
    await state.set_state(State("waiting_for_schedule"))
    await message.reply("لطفاً فاصله زمانی پشتیبان‌گیری را به دقیقه وارد کنید (مثلاً '60' برای هر ساعت):",
                        reply_markup=ReplyKeyboardRemove())


async def process_schedule(message: types.Message, state: FSMContext):
    global backup_interval_minutes
    try:
        interval_minutes = int(message.text)
        backup_interval_minutes = interval_minutes
        config["backup_interval_minutes"] = backup_interval_minutes
        save_config(config)

        # Schedule backup logic here...

        await message.reply(f"زمانبندی پشتیبان‌گیری با موفقیت به هر {interval_minutes} دقیقه تنظیم شد.")
        await state.clear()
    except ValueError:
        await message.reply("فرمت نامعتبر. لطفاً یک عدد به عنوان دقیقه وارد کنید.")


async def handle_restore_backup(message: types.Message):
    if str(message.from_user.id) not in config["admins"] and str(message.from_user.id) != config["ADMIN_CHAT_ID"]:
        await message.reply("شما مجاز به استفاده از این ربات نیستید.")
        return
    await message.reply("لطفاً فایل SQL را برای بازیابی ارسال کنید.")


async def handle_document(message: types.Message):
    if str(message.from_user.id) not in config["admins"] and str(message.from_user.id) != config["ADMIN_CHAT_ID"]:
        await message.reply("شما مجاز به استفاده از این ربات نیستید.")
        return
    document = message.document
    await message.reply("در حال بازیابی دیتابیس...")
    success = await restore_backup(document, bot)
    if success:
        await message.reply("دیتابیس با موفقیت بازیابی شد.")
    else:
        await message.reply("بازیابی با شکست مواجه شد. لطفاً لاگ‌ها را بررسی کنید.")


async def handle_user_traffic_status(message: types.Message):
    if str(message.from_user.id) not in config["admins"] and str(message.from_user.id) != config["ADMIN_CHAT_ID"]:
        await message.reply("شما مجاز به استفاده از این ربات نیستید.")
        return

    await message.reply("در حال ایجاد گزارش وضعیت مصرف کاربران...")
    # Logic for user traffic status...


def register_handlers(dp: Dispatcher):
    dp.message.register(send_welcome, Command("start"))
    dp.message.register(add_admin, lambda message: message.text == "افزودن ادمین")
    dp.message.register(process_new_admin, State("waiting_for_new_admin"))
    dp.message.register(handle_get_backup, lambda message: message.text == "پشتیبان‌گیری فوری")
    dp.message.register(set_backup, lambda message: message.text == "تنظیم فاصله زمانی پشتیبان‌گیری")
    dp.message.register(process_schedule, State("waiting_for_schedule"))
    dp.message.register(handle_restore_backup, lambda message: message.text == "بازیابی پشتیبان")
    dp.message.register(handle_document,
                        lambda message: message.document and message.document.file_name.endswith('.sql'))
    dp.message.register(handle_user_traffic_status, lambda message: message.text == "وضعیت مصرف کاربران")
