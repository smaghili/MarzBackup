import os
import asyncio
import subprocess
from aiogram import Bot
from aiogram.types import FSInputFile
from config import load_config, ADMIN_CHAT_ID, DB_CONTAINER, DB_PASSWORD

config = load_config()

async def create_and_send_backup(bot: Bot):
    try:
        if not ADMIN_CHAT_ID:
            raise ValueError("ADMIN_CHAT_ID is not set in the config file")

        # Check if zip is installed
        if not subprocess.run(['which', 'zip'], capture_output=True, text=True).stdout.strip():
            raise RuntimeError("zip is not installed. Please install it using 'apt-get install zip'")

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
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text="No Marzban or Marzneshin directory found.")
            return False

        os.makedirs(mysql_backup_dir, exist_ok=True)
        
        backup_script = f"""
        #!/bin/bash
        USER="root"
        PASSWORD="{DB_PASSWORD}"
        databases=$(mariadb -h 127.0.0.1 --user=$USER --password=$PASSWORD -e "SHOW DATABASES;" | tr -d "| " | grep -v Database)
        for db in $databases; do
            if [[ "$db" != "information_schema" ]] && [[ "$db" != "mysql" ]] && [[ "$db" != "performance_schema" ]] && [[ "$db" != "sys" ]] ; then
                echo "Dumping database: $db"
                mariadb-dump -h 127.0.0.1 --force --opt --user=$USER --password=$PASSWORD --databases $db > /var/lib/mysql/db-backup/$db.sql
            fi
        done
        """
        
        with open(f"{mysql_backup_dir}/marz-backup.sh", "w") as f:
            f.write(backup_script)
        os.chmod(f"{mysql_backup_dir}/marz-backup.sh", 0o755)
        
        process = await asyncio.create_subprocess_shell(
            f"docker exec {DB_CONTAINER} bash -c '/var/lib/mysql/db-backup/marz-backup.sh'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"Error in backup script: {stderr.decode()}")
        
        # Exclude specific files from the backup
        backup_command = (
            f"zip -r /root/marz-backup-{system}.zip {' '.join(backup_dirs)} {mysql_backup_dir}/* "
            f"-x {mysql_backup_dir}/#mysql50#db-backup.sql -x {mysql_backup_dir}/marz-backup.sh"
        )
        process = await asyncio.create_subprocess_shell(backup_command)
        await process.communicate()
        
        process = await asyncio.create_subprocess_shell(f"zip -ur /root/marz-backup-{system}.zip {mysql_backup_dir}/*.sql")
        await process.communicate()
        
        process = await asyncio.create_subprocess_shell(f"rm -rf {mysql_backup_dir}/*")
        await process.communicate()
        
        caption = f"Backup of {system.capitalize()}\nCreated by @sma16719\nhttps://github.com/smaghili/MarzBackup"
        backup_file = FSInputFile(f"/root/marz-backup-{system}.zip")
        await bot.send_document(chat_id=ADMIN_CHAT_ID, document=backup_file, caption=caption)
        
        print(f"{system.capitalize()} backup completed and sent successfully.")
        return True
    except Exception as e:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"An error occurred during the backup process: {str(e)}")
        print(f"An error occurred during the backup process: {str(e)}")
        return False

async def main():
    bot = Bot(token=config.get('API_TOKEN'))
    try:
        success = await create_and_send_backup(bot)
        if success:
            print("Backup process completed successfully.")
        else:
            print("Backup process failed.")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
