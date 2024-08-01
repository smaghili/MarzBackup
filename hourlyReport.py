import subprocess
import time
import json
import os
from datetime import datetime, timedelta

CONFIG_FILE = '/opt/marzbackup/config.json'
SQL_FILE = '/opt/MarzBackup/hourlyUsage.sql'

def load_config():
    with open(CONFIG_FILE, 'r') as file:
        return json.load(file)

config = load_config()

DB_CONTAINER = config.get('db_container')
DB_PASSWORD = config.get('db_password')
DB_NAME = config.get('db_name')

if not all([DB_CONTAINER, DB_PASSWORD, DB_NAME]):
    raise ValueError("Missing database configuration in config file")

def execute_sql(sql_command):
    full_command = f"docker exec -i {DB_CONTAINER} mariadb -u root -p{DB_PASSWORD} {DB_NAME} -e '{sql_command}'"
    try:
        result = subprocess.run(full_command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        print(f"Error output: {e.stderr}")
        return None

def setup_database():
    if not os.path.exists(SQL_FILE):
        raise FileNotFoundError(f"SQL file not found: {SQL_FILE}")
    
    with open(SQL_FILE, 'r') as file:
        sql_content = file.read()
    
    print("Setting up the database...")
    result = execute_sql(sql_content)
    if result is not None:
        print("Database setup completed successfully.")
    else:
        print("Failed to set up the database.")
        raise RuntimeError("Database setup failed")

# ... (other functions remain the same)

def main():
    print("Starting usage tracking system...")
    print(f"Using database: {DB_NAME} on container: {DB_CONTAINER}")
    
    # Set up the database before starting the main loop
    setup_database()
    
    last_insert = datetime.min
    last_cleanup_check = datetime.min
    
    try:
        while True:
            now = datetime.now()
            
            # Insert usage data and calculate hourly usage every hour
            if now - last_insert >= timedelta(hours=1):
                insert_usage_data()
                calculate_and_display_hourly_usage()
                last_insert = now
            
            # Check for cleanup daily
            if now - last_cleanup_check >= timedelta(days=1):
                if should_run_cleanup():
                    cleanup_old_data()
                last_cleanup_check = now
            
            time.sleep(300)  # Check every 5 minutes
    except KeyboardInterrupt:
        print("Usage tracking system stopped.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise

if __name__ == "__main__":
    main()
