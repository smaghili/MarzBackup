import json
import os

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

config = load_config()

def get_or_ask(key, prompt):
    if key in config:
        return config[key]
    value = input(prompt).strip()
    config[key] = value
    save_config(config)
    return value

# Get API_TOKEN
API_TOKEN = get_or_ask('API_TOKEN', "Please enter your bot token: ")

# Get ADMIN_CHAT_ID
ADMIN_CHAT_ID = get_or_ask('ADMIN_CHAT_ID', "Please enter the admin chat ID: ")

# New fields for database information
MARZBAN_DB_CONTAINER = config.get('marzban_db_container', '')
MARZBAN_DB_PASSWORD = config.get('marzban_db_password', '')
MARZBAN_DB_NAME = config.get('marzban_db_name', '')
MARZNESHIN_DB_CONTAINER = config.get('marzneshin_db_container', '')
MARZNESHIN_DB_PASSWORD = config.get('marzneshin_db_password', '')
MARZNESHIN_DB_NAME = config.get('marzneshin_db_name', '')
