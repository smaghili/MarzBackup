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

# Установка логирования
logging.basicConfig(filename='/var/log/marzbackup.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

router = Router()

@router.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply("به ربات MarzBackup خوش آمدید! لطفاً یکی از گزینه‌های زیر را انتخاب کنید:")

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
        await message.answer("خطایی در فرآیند پشتیبان‌گیری رخ داد. لطفاً لاگ‌ها را بررسی کنید.")
        logging.error(f"Error in backup process: {str(e)}")

# Добавьте здесь другие обработчики, если они есть

def register_handlers(dp: Dispatcher):
    dp.include_router(router)
