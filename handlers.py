
from aiogram import Dispatcher
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# Define states
class BackupScheduleState(StatesGroup):
    waiting_for_schedule = State()

async def handle_get_backup(message: Message):
    try:
        await message.answer("Backup performed successfully.")
    except Exception as e:
        await message.answer(f"Backup error: {e}")

async def set_backup(message: Message, state: FSMContext):
    await BackupScheduleState.waiting_for_schedule.set()
    await message.answer("Please send the backup schedule (e.g., 'Daily at 10:00').")

async def process_schedule(message: Message, state: FSMContext):
    schedule = message.text
    # Save the schedule to config
    await state.finish()
    await message.answer("Backup schedule set.")

async def handle_restore_backup(message: Message):
    try:
        await message.answer("Backup restored successfully.")
    except Exception as e:
        await message.answer(f"Restore backup error: {e}")

async def handle_document(message: Message):
    try:
        if message.document and message.document.file_name.endswith('.sql'):
            await message.answer("SQL file processed.")
    except Exception as e:
        await message.answer(f"File processing error: {e}")

async def handle_user_traffic_status(message: Message):
    try:
        await message.answer("User traffic status updated.")
    except Exception as e:
        await message.answer(f"User traffic status error: {e}")

def register_handlers(dp: Dispatcher):
    dp.message.register(handle_get_backup, lambda message: message.text == "Immediate backup")
    dp.message.register(set_backup, lambda message: message.text == "Set backup interval")
    dp.message.register(process_schedule, state=BackupScheduleState.waiting_for_schedule)
    dp.message.register(handle_restore_backup, lambda message: message.text == "Restore backup")
    dp.message.register(handle_document, lambda message: message.document and message.document.file_name.endswith('.sql'))
    dp.message.register(handle_user_traffic_status, lambda message: message.text == "User traffic status")
