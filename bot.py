import os
import json
import subprocess
import asyncio
import signal
import yaml
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        default_config = {
            "API_TOKEN": "",
            "ADMIN_CHAT_ID": "",
            "backup_interval_minutes": None,
            "db_password": None,
            "admins": []  # لیست برای ذخیره شناسه‌های ادمین
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

config = load_config()
API_TOKEN = config.get("API_TOKEN")
ADMIN_CHAT_ID = config.get("ADMIN_CHAT_ID")
backup_interval_minutes = config.get("backup_interval_minutes")
db_password = config.get("db_password")

class BackupSettings(StatesGroup):
    waiting_for_schedule = State()
    waiting_for_new_admin = State()  # حالت برای انتظار شناسه ادمین جدید

bot = None
dp = None
loop = None
backup_task = None

def get_db_password(system):
    global config, db_password
    if db_password:
        return db_password
    if system == "marzban":
        env_file = "/opt/marzban/.env"
        docker_compose_file = "/opt/marzban/docker-compose.yml"
    else:  # marzneshin
        docker_compose_file = "/etc/opt/marzneshin/docker-compose.yml"
        env_file = None

    password = None
    if env_file and os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                if line.strip().startswith('MARIADB_ROOT_PASSWORD='):
                    password = line.split('=', 1)[1].strip()
                    break

    if not password and os.path.exists(docker_compose_file):
        with open(docker_compose_file, 'r') as f:
            try:
                docker_compose = yaml.safe_load(f)
                if 'services' in docker_compose:
                    for service in docker_compose['services'].values():
                        if 'environment' in service:
                            env = service['environment']
                            if isinstance(env, dict):
                                password = env.get('MARIADB_ROOT_PASSWORD')
                            elif isinstance(env, list):
                                for item in env:
                                    if item.startswith('MARIADB_ROOT_PASSWORD='):
                                        password = item.split('=', 1)[1]
                                        break
                            if password:
                                break
            except yaml.YAMLError as e:
                print(f"Error parsing docker-compose.yml: {e}")

    if password:
        config["db_password"] = password
        save_config(config)
        db_password = password
        return password
    else:
        raise ValueError("Database password not found in configuration files")

def get_db_container_name(system):
    return f"{system}-db-1"

async def create_and_send_backup():
    global bot
    try:
        marzban_dir = subprocess.getoutput("find /opt /root -type d -iname 'marzban' -print -quit")
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

        db_container = get_db_container_name(system)
        password = get_db_password(system)
        os.makedirs(mysql_backup_dir, exist_ok=True)

        backup_script = f"""#!/bin/bash
USER="root"
PASSWORD="{password}"
databases=$(mariadb -h 127.0.0.1 --user=$USER --password=$PASSWORD -e "SHOW DATABASES;" | tr -d "| " | grep -v Database)
for db in $databases; do
    if [[ "$db" != "information_schema" ]] && [[ "$db" != "mysql" ]] && [[ "$db" != "performance_schema" ]] && [[ "$db" != "sys" ]] ; then
        echo "Dumping database: $db"
        mariadb-dump -h 127.0.0.1 --force --opt --user=$USER --password=$PASSWORD --databases $db > /var/lib/mysql/db-backup/$db.sql
    fi
done"""

        with open(f"{mysql_backup_dir}/marz-backup.sh", "w") as f:
            f.write(backup_script)
        os.chmod(f"{mysql_backup_dir}/marz-backup.sh", 0o755)

        subprocess.run(f"docker exec {db_container} bash -c '/var/lib/mysql/db-backup/marz-backup.sh'", shell=True)

        backup_command = f"zip -r /root/marz-backup-{system}.zip {' '.join(backup_dirs)} {mysql_backup_dir}/*"
        subprocess.run(backup_command, shell=True)
        subprocess.run(f"zip -ur /root/marz-backup-{system}.zip {mysql_backup_dir}/*.sql", shell=True)
        subprocess.run(f"rm -rf {mysql_backup_dir}/*", shell=True)

        caption = f"پشتیبان {system.capitalize()}\nایجاد شده توسط @sma16719\nhttps://github.com/smaghili/MarzBackup"
        backup_file = FSInputFile(f"/root/marz-backup-{system}.zip")
        await bot.send_document(chat_id=ADMIN_CHAT_ID, document=backup_file, caption=caption)
        print(f"{system.capitalize()} backup completed and sent successfully.")
        return True
    except Exception as e:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"خطایی در فرآیند پشتیبانگیری رخ داد: {str(e)}")
        print(f"An error occurred during the backup process: {str(e)}")
        return False

async def restore_backup(file: types.Document):
    global bot
    try:
        marzban_dir = subprocess.getoutput("find /opt /root -type d -iname 'marzban' -print -quit")
        marzneshin_dir = "/var/lib/marzneshin"
        if marzban_dir:
            system = "marzban"
            mysql_backup_dir = f"/var/lib/{system}/mysql/db-backup"
            database_name = "marzban"
        elif os.path.isdir(marzneshin_dir):
            system = "marzneshin"
            mysql_backup_dir = "/var/lib/marzneshin/mysql/db-backup"
            database_name = "marzneshin"
        else:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text="هیچ دایرکتوری Marzban یا Marzneshin یافت نشد.")
            return False

        os.makedirs(mysql_backup_dir, exist_ok=True)

        file_info = await bot.get_file(file.file_id)
        file_path = f"{mysql_backup_dir}/{file.file_name}"
        await bot.download_file(file_info.file_path, file_path)

        db_container = get_db_container_name(system)
        password = get_db_password(system)

        restore_command = f"docker exec -i {db_container} mariadb -u root -p\"{password}\" {database_name} < {file_path}"
        result = subprocess.run(restore_command, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"Restore failed: {result.stderr}")

        print(f"{system.capitalize()} database restored successfully.")
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text="دیتابیس با موفقیت بازیابی شد.")
        return True
    except Exception as e:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"خطایی در فرآیند بازیابی رخ داد: {str(e)}")
        print(f"An error occurred during the restore process: {str(e)}")
        return False

async def schedule_backup(interval_minutes):
    while True:
        await create_and_send_backup()
        await asyncio.sleep(interval_minutes * 60)

async def initialize_bot():
    global API_TOKEN, ADMIN_CHAT_ID, bot, dp, loop, config, backup_interval_minutes, backup_task
    if not API_TOKEN:
        API_TOKEN = input("Please enter your bot token: ").strip()
        config["API_TOKEN"] = API_TOKEN
        save_config(config)
    if not ADMIN_CHAT_ID:
        ADMIN_CHAT_ID = input("Please enter the admin chat ID: ").strip()
        config["ADMIN_CHAT_ID"] = ADMIN_CHAT_ID
        save_config(config)

    bot = Bot(token=API_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    @dp.message(Command("start"))
    async def send_welcome(message: types.Message):
        if str(message.from_user.id) not in config["admins"] and str(message.from_user.id) != ADMIN_CHAT_ID:
            await message.reply("شما مجاز به استفاده از این ربات نیستید.")
            return
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="تنظیم فاصله زمانی پشتیبانگیری")],
                [KeyboardButton(text="پشتیبانگیری فوری")],
                [KeyboardButton(text="بازیابی پشتیبان")],
                [KeyboardButton(text="افزودن ادمین")],
                [KeyboardButton(text="وضعیت مصرف کاربران")]
            ],
            resize_keyboard=True
        )
        await message.reply("خوش آمدید! لطفاً یک گزینه را انتخاب کنید:", reply_markup=keyboard)

    @dp.message(lambda message: message.text == "افزودن ادمین")
    async def add_admin(message: types.Message, state: FSMContext):
        if str(message.from_user.id) != ADMIN_CHAT_ID:
            await message.reply("شما مجاز به استفاده از این ربات نیستید.")
            return
        await state.set_state(BackupSettings.waiting_for_new_admin)
        await message.reply("لطفاً شناسه عددی ادمین جدید را وارد کنید:")

    @dp.message(BackupSettings.waiting_for_new_admin)
    async def process_new_admin(message: types.Message, state: FSMContext):
        new_admin_id = message.text.strip()
        if new_admin_id.isdigit():
            config["admins"].append(new_admin_id)
            save_config(config)
            await message.reply(f"ادمین جدید با شناسه {new_admin_id} با موفقیت اضافه شد.")
            await state.clear()
        else:
            await message.reply("لطفاً یک شناسه عددی معتبر وارد کنید.")

    @dp.message(lambda message: message.text == "پشتیبانگیری فوری")
    async def handle_get_backup(message: types.Message):
        if str(message.from_user.id) not in config["admins"] and str(message.from_user.id) != ADMIN_CHAT_ID:
            await message.reply("شما مجاز به استفاده از این ربات نیستید.")
            return
        await message.reply("در حال شروع فرآیند پشتیبانگیری...")
        success = await create_and_send_backup()
        if success:
            await message.reply("پشتیبانگیری با موفقیت انجام و ارسال شد.")
        else:
            await message.reply("پشتیبانگیری با شکست مواجه شد. لطفاً لاگها را بررسی کنید.")

    @dp.message(lambda message: message.text == "تنظیم فاصله زمانی پشتیبانگیری")
    async def set_backup(message: types.Message, state: FSMContext):
        if str(message.from_user.id) not in config["admins"] and str(message.from_user.id) != ADMIN_CHAT_ID:
            await message.reply("شما مجاز به استفاده از این ربات نیستید.")
            return
        await state.set_state(BackupSettings.waiting_for_schedule)
        await message.reply("لطفاً فاصله زمانی پشتیبانگیری را به دقیقه وارد کنید (مثلاً '60' برای هر ساعت):", reply_markup=ReplyKeyboardRemove())

    @dp.message(BackupSettings.waiting_for_schedule)
    async def process_schedule(message: types.Message, state: FSMContext):
        global backup_interval_minutes, backup_task
        try:
            interval_minutes = int(message.text)
            backup_interval_minutes = interval_minutes
            config["backup_interval_minutes"] = backup_interval_minutes
            save_config(config)

            if backup_task:
                backup_task.cancel()
            backup_task = asyncio.create_task(schedule_backup(interval_minutes))

            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="تنظیم فاصله زمانی پشتیبانگیری")],
                    [KeyboardButton(text="پشتیبانگیری فوری")],
                    [KeyboardButton(text="بازیابی پشتیبان")],
                    [KeyboardButton(text="وضعیت مصرف کاربران")]
                ],
                resize_keyboard=True
            )
            await message.reply(f"زمانبندی پشتیبانگیری با موفقیت به هر {interval_minutes} دقیقه تنظیم شد.", reply_markup=keyboard)
            await state.clear()
        except ValueError:
            await message.reply("فرمت نامعتبر. لطفاً یک عدد به عنوان دقیقه وارد کنید.")

    @dp.message(lambda message: message.text == "بازیابی پشتیبان")
    async def handle_restore_backup(message: types.Message):
        if str(message.from_user.id) not in config["admins"] and str(message.from_user.id) != ADMIN_CHAT_ID:
            await message.reply("شما مجاز به استفاده از این ربات نیستید.")
            return
        await message.reply("لطفاً فایل SQL را برای بازیابی ارسال کنید.")

    @dp.message(lambda message: message.document and message.document.file_name.endswith('.sql'))
    async def handle_document(message: types.Message):
        if str(message.from_user.id) not in config["admins"] and str(message.from_user.id) != ADMIN_CHAT_ID:
            await message.reply("شما مجاز به استفاده از این ربات نیستید.")
            return
        document = message.document
        await message.reply("در حال بازیابی دیتابیس...")
        success = await restore_backup(document)
        if success:
            await message.reply("دیتابیس با موفقیت بازیابی شد.")
        else:
            await message.reply("بازیابی با شکست مواجه شد. لطفاً لاگها را بررسی کنید.")

    @dp.message(lambda message: message.text == "وضعیت مصرف کاربران")
    async def handle_user_traffic_status(message: types.Message):
        if str(message.from_user.id) not in config["admins"] and str(message.from_user.id) != ADMIN_CHAT_ID:
            await message.reply("شما مجاز به استفاده از این ربات نیستید.")
            return
        
        await message.reply("در حال ایجاد گزارش وضعیت مصرف کاربران...")
        
        # اجرای کوئری SQL برای دریافت اطلاعات مصرف کاربران
        result = subprocess.run(
            ["docker", "exec", "-i", "marzban-db-1", 
             "mariadb", "-u", "root", "-p12341234", "marzban", "-e",
             "SELECT admins.username AS admin_username, users.username AS user_username, "
             "(users.used_traffic + IFNULL(SUM(user_usage_logs.used_traffic_at_reset), 0)) / 1073741824 AS user_total_traffic_gb, "
             "SUM((users.used_traffic + IFNULL(SUM(user_usage_logs.used_traffic_at_reset), 0))) OVER (PARTITION BY admins.username) / 1073741824 AS admin_total_traffic_gb "
             "FROM admins LEFT JOIN users ON users.admin_id = admins.id LEFT JOIN user_usage_logs ON user_usage_logs.user_id = users.id "
             "WHERE admins.username = 'mahdi206' GROUP BY admins.username, users.username, users.used_traffic ORDER BY user_total_traffic_gb DESC"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
        )
        
        if result.returncode != 0:
            await message.reply("خطایی در اجرای کوئری SQL رخ داد.")
            return
        
        # ذخیره خروجی کوئری در فایل CSV
        with open('/root/output.csv', 'w') as f:
            f.write("Admin Username,User Username,User Total Traffic GB,Admin Total Traffic GB\n")
            f.write(result.stdout.replace('\t', ','))
        
        # تبدیل فایل CSV به عکس با استفاده از convert2pic.py
        subprocess.run(["python3", "/root/convert2pic.py"])
        
        # ارسال عکس به چت ادمین
        photo = FSInputFile('/root/output_table.png')
        await bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=photo, caption="وضعیت مصرف کاربران شما بدین صورت است:")
        
        await message.reply("گزارش وضعیت مصرف کاربران ارسال شد.")

def shutdown_handler(signum, frame):
    print("Shutting down...")
    if backup_task:
        backup_task.cancel()
    loop.stop()

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

async def main():
    global loop
    print("Bot is starting...")
    loop = asyncio.get_event_loop()
    await initialize_bot()
    if backup_interval_minutes:
        backup_task = asyncio.create_task(schedule_backup(backup_interval_minutes))
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
