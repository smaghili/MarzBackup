import json
import os

CONFIG_FILE_PATH = 'config.json'

def load_config():
    try:
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
