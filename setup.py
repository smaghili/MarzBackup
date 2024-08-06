import json
import os
import sys
from config import get_or_ask, save_config, load_config
from aiogram import Bot
import asyncio
import subprocess

async def validate_token(token):
    try:
        bot = Bot(token=token)
        await bot.get_me()
        await bot.session.close()
        return True
    except Exception as e:
        print(f"Invalid bot token: {e}")
        return False

async def validate_chat_id(token, chat_id):
    try:
        bot = Bot(token=token)
        await bot.send_message(chat_id=chat_id, text="Validating admin chat ID...")
        await bot.session.close()
        return True
    except Exception as e:
        print(f"Invalid admin chat ID: {e}")
        return False

async def setup():
    config = load_config()
    
    # Get and validate API_TOKEN
    while True:
        API_TOKEN = get_or_ask('API_TOKEN', "Please enter your Telegram bot token: ")
        if await validate_token(API_TOKEN):
            break
        else:
            del config['API_TOKEN']
            save_config(config)
    
    # Get and validate ADMIN_CHAT_ID
    while True:
        ADMIN_CHAT_ID = get_or_ask('ADMIN_CHAT_ID', "Please enter the admin chat ID: ")
        if await validate_chat_id(API_TOKEN, ADMIN_CHAT_ID):
            break
        else:
            del config['ADMIN_CHAT_ID']
            save_config(config)
    
    print("Setup completed successfully.")
    
    # Update backup cron job after setup
    update_backup_cron_command = "marzbackup update_backup_interval"
    process = await asyncio.create_subprocess_shell(
        update_backup_cron_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode == 0:
        print("Backup cron job updated successfully.")
    else:
        print(f"Error updating backup cron job: {stderr.decode()}")

if __name__ == "__main__":
    asyncio.run(setup())
