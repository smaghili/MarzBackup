import os
import asyncio
import subprocess
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
        [types.KeyboardButton(text="Immediate Backup")],
        [types.KeyboardButton(text="Set Backup Interval")],
        [types.KeyboardButton(text="Restore Backup")],
        [types.KeyboardButton(text="Change User Usage Report Interval")]
    ],
    resize_keyboard=True
)

@router.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply("Welcome to MarzBackup bot! Please select one of the options below:", reply_markup=keyboard)

@router.message(F.text == "Immediate Backup")
async def handle_get_backup(message: types.Message):
    await message.answer("Creating backup... Please wait.")
    try:
        process = await asyncio.create_subprocess_shell(
            "/usr/bin/python3 /opt/MarzBackup/backup.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            await message.answer("Backup successfully created and sent.")
        else:
            await message.answer(f"An error occurred during the backup process: {stderr.decode()}")
    except Exception as e:
        await message.answer(f"Error in backup process: {e}")

@router.message(F.text == "Set Backup Interval")
async def set_backup(message: types.Message, state: FSMContext):
    await state.set_state(BackupStates.waiting_for_schedule)
    await message.answer("Please send the backup interval in minutes (e.g., '10' for every 10 minutes).")

@router.message(BackupStates.waiting_for_schedule)
async def process_schedule(message: types.Message, state: FSMContext):
    try:
        minutes = int(message.text)
        if minutes <= 0:
            raise ValueError("Minutes must be a positive number.")
        
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
            await message.answer(f"Backup interval set to every {minutes} minutes.")
        else:
            await message.answer(f"Error setting backup interval: {stderr.decode()}")
    except ValueError:
        await message.answer("Please enter a valid positive integer for minutes.")
    finally:
        await state.clear()

@router.message(F.text == "Restore Backup")
async def request_sql_file(message: types.Message, state: FSMContext):
    await state.set_state(BackupStates.waiting_for_sql_file)
    await message.answer("Please send the backup SQL file.")

@router.message(BackupStates.waiting_for_sql_file)
async def process_sql_file(message: types.Message, state: FSMContext):
    if not message.document:
        await message.answer("Please send a file.")
        return
    
    if not message.document.file_name.lower().endswith('.sql'):
        await message.answer("Invalid file type. Please send a .sql file.")
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
            await message.answer("Database information not found in config file.")
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
            await message.answer("Database successfully restored.")
        else:
            await message.answer(f"Error restoring database: {stderr.decode()}")

    except Exception as e:
        await message.answer(f"Error processing SQL file: {e}")
    finally:
        await state.clear()

@router.message(F.text == "Change User Usage Report Interval")
async def change_report_interval(message: types.Message, state: FSMContext):
    await state.set_state(ReportIntervalStates.waiting_for_interval)
    await message.answer("Please enter the user usage report interval in minutes (Note: Short intervals may increase database size. Recommended value is 60):")

@router.message(ReportIntervalStates.waiting_for_interval)
async def process_report_interval(message: types.Message, state: FSMContext):
    try:
        interval = int(message.text)
        if interval <= 0:
            raise ValueError("Interval must be a positive number.")
        
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
            await message.answer(f"User usage report interval set to {interval} minutes and the reporting system has been restarted.")
        else:
            await message.answer(f"Error setting report interval: {stderr.decode()}")
    except ValueError:
        await message.answer("Please enter a valid positive integer.")
    finally:
        await state.clear()

def register_handlers(dp: Dispatcher):
    dp.include_router(router)
