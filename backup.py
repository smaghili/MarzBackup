import os
import subprocess
import yaml
from aiogram.types import FSInputFile
from config import load_config, save_config

config = load_config()

def get_db_password(system):
    try:
        env_file = "/opt/marzban/.env" if system == "marzban" else None
        docker_compose_file = "/opt/marzban/docker-compose.yml" if system == "marzban" else "/etc/opt/marzneshin/docker-compose.yml"

        password = None
        if env_file and os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if line.strip().startswith('MARIADB_ROOT_PASSWORD='):
                        password = line.split('=', 1)[1].strip()
                        break

        if not password and os.path.exists(docker_compose_file):
            with open(docker_compose_file, 'r') as f:
                docker_compose = yaml.safe_load(f)
                for service in docker_compose.get('services', {}).values():
                    env = service.get('environment', {})
                    if isinstance(env, dict):
                        password = env.get('MARIADB_ROOT_PASSWORD')
                    elif isinstance(env, list):
                        for item in env:
                            if item.startswith('MARIADB_ROOT_PASSWORD='):
                                password = item.split('=', 1)[1]
                                break
                    if password:
                        break

        if password:
            config["db_password"] = password
            save_config(config)
            return password
        else:
            raise ValueError("Database password not found in configuration files")
    except Exception as e:
        raise RuntimeError(f"Failed to get DB password: {e}")

def get_db_container_id(system):
    try:
        output = subprocess.check_output(['docker', 'ps', '-a']).decode()
        for line in output.split('\n'):
            if system in line:
                return line.split()[0]
        raise ValueError("No running container found for the specified system")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get DB container ID: {e}")

def backup_database(system):
    try:
        password = get_db_password(system)
        container_id = get_db_container_id(system)
        backup_file = f"/opt/marzban/{system}-backup.sql" if system == "marzban" else "/etc/opt/marzneshin/{system}-backup.sql"

        subprocess.run([
            'docker', 'exec', container_id, 'mysqldump', '-u', 'root', 
            f'--password={password}', '--all-databases', 
            '--skip-lock-tables', '--routines', '--events', '--triggers', 
            '-r', backup_file
        ], check=True)

        return backup_file
    except Exception as e:
        raise RuntimeError(f"Failed to backup database: {e}")

def send_backup_to_admin(system, bot, admin_chat_id):
    try:
        backup_file = backup_database(system)
        document = FSInputFile(backup_file)
        bot.send_document(chat_id=admin_chat_id, document=document)
    except Exception as e:
        raise RuntimeError(f"Failed to send backup to admin: {e}")
