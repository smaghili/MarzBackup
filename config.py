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

def get_db_container_name(system):
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
        for service_name, service_config in services.items():
            if 'mariadb' in service_name.lower() or ('image' in service_config and 'mariadb' in service_config['image'].lower()):
                return f"{os.path.basename(os.path.dirname(compose_file))}-{service_name}-1"
    except Exception as e:
        print(f"Error reading docker-compose.yml: {e}")
    
    return ""  # Return empty string if not found

def get_db_password(system):
    if system == "marzban":
        env_file = "/opt/marzban/.env"
    elif system == "marzneshin":
        env_file = "/etc/opt/marzneshin/.env"
    else:
        raise ValueError(f"Unknown system: {system}")

    try:
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith('MYSQL_ROOT_PASSWORD='):
                    return line.split('=', 1)[1].strip()
    except Exception as e:
        print(f"Error reading .env file: {e}")
    
    return ""  # Return empty string if not found

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

    try:
        # Update db_container
        db_container = get_db_container_name(system)
        if config.get("db_container") != db_container:
            config["db_container"] = db_container
            updated = True

        # Update db_password
        db_password = get_db_password(system)
        if config.get("db_password") != db_password:
            config["db_password"] = db_password
            updated = True

        # Update db_name
        db_name = get_db_name(system)
        if config.get("db_name") != db_name:
            config["db_name"] = db_name
            updated = True

    except Exception as e:
        print(f"Error updating config: {str(e)}")

    if updated:
        save_config(config)
        print("Config file updated with correct values")
    else:
        print("Config file is up to date")

# Load existing config
config = load_config()

# Get API_TOKEN
API_TOKEN = get_or_ask('API_TOKEN', "Please enter your bot token: ")

# Get ADMIN_CHAT_ID
ADMIN_CHAT_ID = get_or_ask('ADMIN_CHAT_ID', "Please enter the admin chat ID: ")

# Update the config with latest database information
update_config()

# Other database fields (now using generic names)
DB_CONTAINER = config.get('db_container', '')
DB_PASSWORD = config.get('db_password', '')
DB_NAME = config.get('db_name', '')

# Add this line at the end of the file
INSTALLED_VERSION = get_installed_version()

# Run update_config at the start of the program
if __name__ == "__main__":
    update_config()
