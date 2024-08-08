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

# Logging configuration
logging.basicConfig(filename='/var/log/marzbackup.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

router = Router()

@router.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply("به ربات MarzBackup خوش آمدید! لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=keyboard")

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
                    await message.answer("خطا در ارسال فایل. لطفاً با پشتیبانی تماس بگیرید.")
            else:
                logging.error(f"Backup file not found: {backup_file_path}")
                await message.answer("خطا در ایجاد فایل پشتیبان. لطفاً با پشتیبانی تماس بگیرید.")
        else:
            error_message = stderr.decode().strip()
            logging.error(f"Backup creation failed: {error_message}")
            await message.answer("خطا در ایجاد پشتیبان. لطفاً با پشتیبانی تماس بگیرید.")
    
    except Exception as e:
        logging.exception(f"Error in backup process: {str(e)}")
        await message.answer("خطایی در فرآیند پشتیبان‌گیری رخ داد. لطفاً با پشتیبانی تماس بگیرید.")

# Add other handlers here if needed

def register_handlers(dp: Dispatcher):
    dp.include_router(router)
