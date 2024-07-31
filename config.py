import json
import os
import yaml

CONFIG_FILE_PATH = '/opt/marzbackup/config.json'

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

def get_or_ask(key, prompt):
    config = load_config()
    if key in config:
        return config[key]
    value = input(prompt).strip()
    config[key] = value
    save_config(config)
    return value

def get_db_name(system):
    if system == "marzban":
        compose_file = "/opt/marzban/docker-compose.yml"
    elif system == "marzneshin":
        compose_file = "/etc/opt/marzneshin/docker-compose.yml"
    else:
        raise ValueError(f"Unknown system: {system}")

    try:
        with open(compose_file, 'r') as f:
            compose_config = yaml.safe_load(f)
        
        services = compose_config.get('services', {})
        for service in services.values():
            environment = service.get('environment', {})
            if isinstance(environment, list):
                for env in environment:
                    if env.startswith('MARIADB_DATABASE='):
                        return env.split('=', 1)[1].strip()
            elif isinstance(environment, dict):
                if 'MARIADB_DATABASE' in environment:
                    return environment['MARIADB_DATABASE']
    except Exception as e:
        print(f"Error reading docker-compose.yml: {e}")
    
    return system  # default to system name if not found

# Load existing config
config = load_config()

# Get API_TOKEN
API_TOKEN = get_or_ask('API_TOKEN', "Please enter your bot token: ")

# Get ADMIN_CHAT_ID
ADMIN_CHAT_ID = get_or_ask('ADMIN_CHAT_ID', "Please enter the admin chat ID: ")

# Determine the system and get the database name
system = "marzban" if os.path.exists("/opt/marzban") else "marzneshin"
db_name = get_db_name(system)

# Save the database name in the config
config[f'{system}_db_name'] = db_name
save_config(config)

# Other database fields
MARZBAN_DB_CONTAINER = config.get('marzban_db_container', '')
MARZBAN_DB_PASSWORD = config.get('marzban_db_password', '')
MARZBAN_DB_NAME = config.get('marzban_db_name', '')
MARZNESHIN_DB_CONTAINER = config.get('marzneshin_db_container', '')
MARZNESHIN_DB_PASSWORD = config.get('marzneshin_db_password', '')
MARZNESHIN_DB_NAME = config.get('marzneshin_db_name', '')
