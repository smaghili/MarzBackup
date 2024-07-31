import os
import asyncio
import subprocess
import yaml
from aiogram import Router, F, Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import save_config, load_config
from backup import handle_backup, create_and_send_backup

# Define states
class BackupStates(StatesGroup):
    waiting_for_schedule = State()
    waiting_for_sql_file = State()

# Create a router instance
router = Router()

# Create a keyboard markup
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="پشتیبان‌گیری فوری")],
        [KeyboardButton(text="تنظیم فاصله زمانی پشتیبان‌گیری")],
        [KeyboardButton(text="بازیابی پشتیبان")]
    ],
    resize_keyboard=True
)

# ... (سایر توابع بدون تغییر باقی می‌مانند)

async def extract_db_info(system):
    config = load_config()
    
    # Extract container name
    container_name = config.get(f"{system}_db_container")
    if not container_name:
        if system == "marzban":
            compose_file = "/opt/marzban/docker-compose.yml"
        elif system == "marzneshin":
            compose_file = "/etc/opt/marzneshin/docker-compose.yml"
        else:
            raise ValueError(f"Unknown system: {system}")

        with open(compose_file, 'r') as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get('services', {})
        for service_name, service_config in services.items():
            if 'mariadb' in service_name.lower() or ('image' in service_config and 'mariadb' in service_config['image'].lower()):
                container_name = f"{system}-{service_name}-1"
                config[f"{system}_db_container"] = container_name
                break

    # Extract database password
    db_password = config.get(f"{system}_db_password")
    if not db_password:
        if system == "marzban":
            env_file = "/opt/marzban/.env"
        elif system == "marzneshin":
            env_file = "/etc/opt/marzneshin/.env"

        with open(env_file, 'r') as f:
            for line in f:
                if line.strip().startswith('MARIADB_ROOT_PASSWORD='):
                    db_password = line.split('=', 1)[1].strip()
                    config[f"{system}_db_password"] = db_password
                    break

    # Extract database name
    db_name = config.get(f"{system}_db_name")
    if not db_name:
        with open(compose_file, 'r') as f:
            compose_config = yaml.safe_load(f)
        
        services = compose_config.get('services', {})
        for service_config in services.values():
            environment = service_config.get('environment', {})
            if isinstance(environment, list):
                for env in environment:
                    if env.startswith('MARIADB_DATABASE='):
                        db_name = env.split('=', 1)[1].strip()
                        config[f"{system}_db_name"] = db_name
                        break
            elif isinstance(environment, dict):
                db_name = environment.get('MARIADB_DATABASE')
                if db_name:
                    config[f"{system}_db_name"] = db_name
                    break

    save_config(config)
    return container_name, db_password, db_name

@router.message(BackupStates.waiting_for_sql_file, F.document)
async def process_sql_file(message: Message, state: FSMContext):
    try:
        if not message.document.file_name.lower().endswith('.sql'):
            await message.answer("لطفاً یک فایل با پسوند .sql ارسال کنید.")
            return

        # Determine the system and backup directory
        marzban_dir = "/opt/marzban"
        marzneshin_dir = "/etc/opt/marzneshin"
        if os.path.exists(marzban_dir):
            system = "marzban"
            backup_dir = "/var/lib/marzban/mysql/db-backup"
        elif os.path.exists(marzneshin_dir):
            system = "marzneshin"
            backup_dir = "/var/lib/marzneshin/mysql/db-backup"
        else:
            await message.answer("خطا: سیستم مرزبان یا مرزنشین شناسایی نشد.")
            await state.clear()
            return

        # Create backup directory if it doesn't exist
        os.makedirs(backup_dir, exist_ok=True)

        # Download and save the file
        file = await message.bot.get_file(message.document.file_id)
        file_path = os.path.join(backup_dir, message.document.file_name)
        await message.bot.download_file(file.file_path, file_path)

        await message.answer(f"فایل SQL با موفقیت در مسیر {file_path} ذخیره شد.")

        # Extract database information
        container_name, db_password, db_name = await extract_db_info(system)

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

def register_handlers(dp: Dispatcher):
    dp.include_router(router)
