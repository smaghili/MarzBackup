import os
import yaml

CONFIG_FILE_PATH = 'config.yml'

def load_config():
    try:
        with open(CONFIG_FILE_PATH, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as e:
        raise RuntimeError(f"Error loading config file: {e}")

def save_config(config):
    try:
        with open(CONFIG_FILE_PATH, 'w') as file:
            yaml.safe_dump(config, file)
    except yaml.YAMLError as e:
        raise RuntimeError(f"Error saving config file: {e}")
