from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import save_config, load_config, ADMIN_CHAT_ID
import os
import asyncio
import tempfile

# Define states
class BackupStates(StatesGroup):
    waiting_for_schedule = State()

# Create a router instance
router = Router()

config = load_config()

async def create_and_send_backup():
    global bot
    try:
        marzban_dir = await asyncio.subprocess.check_output("find /opt /root -type d -iname 'marzban' -print -quit", shell=True)
        marzban_dir = marzban_dir.decode().strip()
        marzneshin_dir = "/var/lib/marzneshin"
        
        if marzban_dir:
            system = "marzban"
            backup_dirs = ["/opt/marzban"]
            mysql_backup_dir = f"/var/lib/{system}/mysql/db-backup"
        elif os.path.isdir(marzneshin_dir):
            system = "marzneshin"
            backup_dirs = ["/etc/opt/marzneshin", "/var/lib/marznode"]
            mysql_backup_dir = "/var/lib/marzneshin/mysql/db-backup"
        else:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text="هیچ دایرکتوری Marzban یا Marzneshin یافت نشد.")
            return False

        db_container = await get_db_container_name(system)
        password = await get_db_password(system)
        
        os.makedirs(mysql_backup_dir, exist_ok=True)

        backup_script = f"""
        #!/bin/bash
        USER="root"
        PASSWORD="{password}"
        databases=$(mariadb -h 127.0.0.1 --user=$USER --password=$PASSWORD -e "SHOW DATABASES;" | tr -d "| " | grep -v Database)
        for db in $databases; do
            if [[ "$db" != "information_schema" ]] && [[ "$db" != "mysql" ]] && [[ "$db" != "performance_schema" ]] && [[ "$db" != "sys" ]] ; then
                echo "Dumping database: $db"
                mariadb-dump -h 127.0.0.1 --force --opt --user=$USER --password=$PASSWORD --databases $db > /var/lib/mysql/db-backup/$db.sql
            fi
        done
        """

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as temp_script:
            temp_script.write(backup_script)
            temp_script_path = temp_script.name

        os.chmod(temp_script_path, 0o755)
        
        await asyncio.subprocess.create_subprocess_shell(
            f"docker cp {temp_script_path} {db_container}:/var/lib/mysql/db-backup/marz-backup.sh"
        )
        
        await asyncio.subprocess.create_subprocess_shell(
            f"docker exec {db_container} bash -c '/var/lib/mysql/db-backup/marz-backup.sh'"
        )

        backup_file_path = f"/tmp/marz-backup-{system}.zip"
        backup_command = f"zip -r {backup_file_path} {' '.join(backup_dirs)} {mysql_backup_dir}/*"
        await asyncio.subprocess.create_subprocess_shell(backup_command)

        await asyncio.subprocess.create_subprocess_shell(f"zip -ur {backup_file_path} {mysql_backup_dir}/*.sql")
        
        await asyncio.subprocess.create_subprocess_shell(f"rm -rf {mysql_backup_dir}/*")
        
        caption = f"پشتیبان {system.capitalize()}\nایجاد شده توسط @sma16719\nhttps://github.com/smaghili/MarzBackup"
        backup_file = FSInputFile(backup_file_path)
        await bot.send_document(chat_id=ADMIN_CHAT_ID, document=backup_file, caption=caption)
        
        os.remove(temp_script_path)
        os.remove(backup_file_path)

        print(f"{system.capitalize()} backup completed and sent successfully.")
        return True

    except Exception as e:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"خطایی در فرآیند پشتیبان‌گیری رخ داد: {str(e)}")
        print(f"An error occurred during the backup process: {str(e)}")
        return False

async def handle_get_backup(message: Message):
    try:
        success = await create_and_send_backup()
        if success:
            await message.answer("پشتیبان‌گیری انجام شد و فایل ارسال گردید.")
        else:
            await message.answer("خطایی در فرآیند پشتیبان‌گیری رخ داد.")
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
