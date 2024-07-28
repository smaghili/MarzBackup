import os
import subprocess
import yaml
from aiogram.types import FSInputFile
from config import load_config, save_config

config = load_config()

def get_db_password(system):
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
        return password
    else:
        raise ValueError("Database password not found in configuration files")

def get_db_container_name(system):
    return f"{system}-db-1"

async def create_and_send_backup(bot):
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
            await bot.send_message(chat_id=config["ADMIN_CHAT_ID"], text="هیچ دایرکتوری Marzban یا Marzneshin یافت نشد.")
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
        await bot.send_document(chat_id=config["ADMIN_CHAT_ID"], document=backup_file, caption=caption)
        print(f"{system.capitalize()} backup completed and sent successfully.")
        return True
    except Exception as e:
        await bot.send_message(chat_id=config["ADMIN_CHAT_ID"], text=f"خطایی در فرآیند پشتیبانگیری رخ داد: {str(e)}")
        print(f"An error occurred during the backup process: {str(e)}")
        return False

async def restore_backup(file, bot):
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
            await bot.send_message(chat_id=config["ADMIN_CHAT_ID"], text="هیچ دایرکتوری Marzban یا Marzneshin یافت نشد.")
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
        await bot.send_message(chat_id=config["ADMIN_CHAT_ID"], text="دیتابیس با موفقیت بازیابی شد.")
        return True
    except Exception as e:
        await bot.send_message(chat_id=config["ADMIN_CHAT_ID"], text=f"خطایی در فرآیند بازیابی رخ داد: {str(e)}")
        print(f"An error occurred during the restore process: {str(e)}")
        return False
