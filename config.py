import json
import os
import yaml

CONFIG_FILE_PATH = '/opt/marzbackup/config.json'
VERSION_FILE_PATH = '/opt/marzbackup/version.json'

def load_config():
    try:
        if not os.path.exists(os.path.dirname(CONFIG_FILE_PATH)):
            os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
        
        if not os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, 'w') as file:
                json.dump({}, file)
        
        with open(CONFIG_FILE_PATH, 'r') as file:
            config = json.load(file)
        return config
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"Error loading config file: {e}")
        return {}

def save_config(config):
    try:
        with open(CONFIG_FILE_PATH, 'w') as file:
            json.dump(config, file, indent=4)
    except Exception as e:
        print(f"Error saving config file: {e}")

def get_installed_version():
    try:
        with open(VERSION_FILE_PATH, 'r') as file:
            version_info = json.load(file)
        return version_info.get('installed_version', 'stable')
    except FileNotFoundError:
        return 'stable'
    except json.JSONDecodeError:
        return 'stable'

def get_or_ask(key, prompt):
    config = load_config()
    if key in config:
        return config[key]
    value = input(prompt).strip()
    config[key] = value
    save_config(config)
    return value

def get_db_info(system):
    if system == "marzban":
        compose_file = "/opt/marzban/docker-compose.yml"
        env_file = "/opt/marzban/.env"
    elif system == "marzneshin":
        compose_file = "/etc/opt/marzneshin/docker-compose.yml"
        env_file = "/etc/opt/marzneshin/.env"
    else:
        raise ValueError(f"Unknown system: {system}")

    db_container = ""
    db_password = ""
    db_name = ""
    db_type = ""

    # Get container name and database type from docker-compose.yml
    try:
        with open(compose_file, 'r') as f:
            compose_config = yaml.safe_load(f)
        services = compose_config.get('services', {})
        for service_name, service_config in services.items():
            if 'mariadb' in service_name.lower() or ('image' in service_config and 'mariadb' in service_config['image'].lower()):
                db_container = f"{os.path.basename(os.path.dirname(compose_file))}-{service_name}-1"
                db_type = "mariadb"
                break
            elif 'mysql' in service_name.lower() or ('image' in service_config and 'mysql' in service_config['image'].lower()):
                db_container = f"{os.path.basename(os.path.dirname(compose_file))}-{service_name}-1"
                db_type = "mysql"
                break
    except Exception as e:
        print(f"Error reading docker-compose.yml: {e}")

    # Get password and database name from .env file
    try:
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith(('MARIADB_ROOT_PASSWORD=', 'MYSQL_ROOT_PASSWORD=', 'DB_PASSWORD=')):
                    db_password = line.split('=', 1)[1].strip()
                elif line.startswith(('MARIADB_DATABASE=', 'MYSQL_DATABASE=', 'DB_NAME=')):
                    db_name = line.split('=', 1)[1].strip()
    except Exception as e:
        print(f"Error reading .env file: {e}")

    # If db_name is not found in .env, use the system name as default
    if not db_name:
        db_name = system

    # If we still don't have a password, try to get it from docker-compose.yml
    if not db_password:
        try:
            for service in services.values():
                environment = service.get('environment', {})
                if isinstance(environment, list):
                    for env in environment:
                        if env.startswith(('MARIADB_ROOT_PASSWORD=', 'MYSQL_ROOT_PASSWORD=', 'DB_PASSWORD=')):
                            db_password = env.split('=', 1)[1].strip()
                            break
                elif isinstance(environment, dict):
                    db_password = environment.get('MARIADB_ROOT_PASSWORD') or environment.get('MYSQL_ROOT_PASSWORD') or environment.get('DB_PASSWORD', '')
                if db_password:
                    break
        except Exception as e:
            print(f"Error reading password from docker-compose.yml: {e}")

    return db_container, db_password, db_name, db_type

def update_config():
    config = load_config()
    updated = False

    # Determine the system (marzban or marzneshin)
    if os.path.exists("/opt/marzban"):
        system = "marzban"
    elif os.path.exists("/etc/opt/marzneshin"):
        system = "marzneshin"
    else:
        print("Neither Marzban nor Marzneshin installation found.")
        return

    db_container, db_password, db_name, db_type = get_db_info(system)

    # Update db_container
    if config.get("db_container") != db_container:
        config["db_container"] = db_container
        updated = True

    # Update db_password
    if config.get("db_password") != db_password:
        config["db_password"] = db_password
        updated = True

    # Update db_name
    if config.get("db_name") != db_name:
        config["db_name"] = db_name
        updated = True

    # Update db_type
    if config.get("db_type") != db_type:
        config["db_type"] = db_type
        updated = True

    # Remove old system-specific keys
    for old_key in ["marzban_db_container", "marzban_db_password", "marzban_db_name",
                    "marzneshin_db_container", "marzneshin_db_password", "marzneshin_db_name"]:
        if old_key in config:
            del config[old_key]
            updated = True

    if updated:
        save_config(config)
        print("Config file updated with correct values")
    else:
        print("Config file is up to date")

def get_db_name():
    config = load_config()
    return config.get('db_name', '')

# Load existing config
config = load_config()

# Get API_TOKEN
API_TOKEN = get_or_ask('API_TOKEN', "Please enter your bot token: ")

# Get ADMIN_CHAT_ID
ADMIN_CHAT_ID = get_or_ask('ADMIN_CHAT_ID', "Please enter the admin chat ID: ")

# Update the config with latest database information
update_config()

# Reload config after update
config = load_config()

# Get database fields
DB_CONTAINER = config.get('db_container', '')
DB_PASSWORD = config.get('db_password', '')
DB_NAME = get_db_name()
DB_TYPE = config.get('db_type', '')

# Add this line at the end of the file
INSTALLED_VERSION = get_installed_version()

# Run update_config at the start of the program
if __name__ == "__main__":
    update_config()
