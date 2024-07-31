import os
import asyncio
import subprocess
import yaml
from aiogram.types import FSInputFile
from config import load_config, save_config, ADMIN_CHAT_ID

config = load_config()

async def get_db_container_name(system):
    try:
        # First, check if the container name is already in the config
        container_name = config.get(f"{system}_db_container")
        if container_name:
            # Verify if the container is still running
            result = await asyncio.create_subprocess_shell(
                f"docker ps --format '{{{{.Names}}}}' | grep {container_name}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            if stdout:
                return container_name
        
        # If not in config or not running, find it from docker-compose.yml
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
                # Construct the container name
                project_name = os.path.basename(os.path.dirname(compose_file))
                container_name = f"{project_name}-{service_name}-1"
                
                # Check if the container is running
                result = await asyncio.create_subprocess_shell(
                    f"docker ps --format '{{{{.Names}}}}' | grep {container_name}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await result.communicate()
                if stdout:
                    # Save the container name in the config
                    config[f"{system}_db_container"] = container_name
                    save_config(config)
                    return container_name

        raise ValueError(f"No running MariaDB container found for {system}")
    except Exception as e:
        raise RuntimeError(f"Failed to get DB container name: {e}")

def get_db_password(system):
    try:
        # First, check if the password is already in the config
        password = config.get(f"{system}_db_password")
        if password:
            return password

        if system == "marzban":
            env_file = "/opt/marzban/.env"
            compose_file = "/opt/marzban/docker-compose.yml"
        elif system == "marzneshin":
            env_file = "/etc/opt/marzneshin/.env"
            compose_file = "/etc/opt/marzneshin/docker-compose.yml"
        else:
            raise ValueError(f"Unknown system: {system}")

        # Check .env file
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if line.strip().startswith('MARIADB_ROOT_PASSWORD='):
                        password = line.split('=', 1)[1].strip()
                        config[f"{system}_db_password"] = password
                        save_config(config)
                        return password

        # Check docker-compose.yml file
        if os.path.exists(compose_file):
            with open(compose_file, 'r') as f:
                compose_config = yaml.safe_load(f)
                services = compose_config.get('services', {})
                for service in services.values():
                    environment = service.get('environment', {})
                    if isinstance(environment, list):
                        for env in environment:
                            if env.startswith('MARIADB_ROOT_PASSWORD='):
                                password = env.split('=', 1)[1].strip()
                                config[f"{system}_db_password"] = password
                                save_config(config)
                                return password
                    elif isinstance(environment, dict):
                        if 'MARIADB_ROOT_PASSWORD' in environment:
                            password = environment['MARIADB_ROOT_PASSWORD']
                            config[f"{system}_db_password"] = password
                            save_config(config)
                            return password

        raise ValueError("Database password (MARIADB_ROOT_PASSWORD) not found in .env or docker-compose.yml files")
    except Exception as e:
        raise RuntimeError(f"Failed to get DB password: {e}")

async def create_and_send_backup(bot):
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
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text="هیچ دایرکتوری Marzban یا Marzneshin یافت نشد.")
            return False

        db_container = await get_db_container_name(system)
        password = get_db_password(system)
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
        
        with open(f"{mysql_backup_dir}/marz-backup.sh", "w") as f:
            f.write(backup_script)
        os.chmod(f"{mysql_backup_dir}/marz-backup.sh", 0o755)
        
        process = await asyncio.create_subprocess_shell(
            f"docker exec {db_container} bash -c '/var/lib/mysql/db-backup/marz-backup.sh'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"Error in backup script: {stderr.decode()}")
        
        backup_command = f"zip -r /root/marz-backup-{system}.zip {' '.join(backup_dirs)} {mysql_backup_dir}/*"
        process = await asyncio.create_subprocess_shell(backup_command)
        await process.communicate()
        
        process = await asyncio.create_subprocess_shell(f"zip -ur /root/marz-backup-{system}.zip {mysql_backup_dir}/*.sql")
        await process.communicate()
        
        process = await asyncio.create_subprocess_shell(f"rm -rf {mysql_backup_dir}/*")
        await process.communicate()
        
        caption = f"پشتیبان {system.capitalize()}\nایجاد شده توسط @sma16719\nhttps://github.com/smaghili/MarzBackup"
        backup_file = FSInputFile(f"/root/marz-backup-{system}.zip")
        await bot.send_document(chat_id=ADMIN_CHAT_ID, document=backup_file, caption=caption)
        
        print(f"{system.capitalize()} backup completed and sent successfully.")
        return True
    except Exception as e:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"خطایی در فرآیند پشتیبان‌گیری رخ داد: {str(e)}")
        print(f"An error occurred during the backup process: {str(e)}")
        return False

async def handle_backup(bot):
    return await create_and_send_backup(bot)
