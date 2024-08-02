import subprocess
import time
import json
import os
import logging
from datetime import datetime, timedelta
from config import load_config, CONFIG_FILE_PATH

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

INSTALL_DIR = "/opt/MarzBackup"
SQL_FILE = os.path.join(INSTALL_DIR, 'hourlyUsage.sql')

def load_config():
    with open(CONFIG_FILE_PATH, 'r') as file:
        return json.load(file)

config = load_config()

DB_CONTAINER = config.get('db_container')
DB_PASSWORD = config.get('db_password')
MARZBAN_DB = 'marzban'

if not all([DB_CONTAINER, DB_PASSWORD]):
    raise ValueError("Missing database configuration in config file")

def execute_sql(sql_command, db_name='user_usage_tracking'):
    escaped_command = sql_command.replace('"', '\\"').replace('`', '\\`')
    full_command = f"docker exec -i {DB_CONTAINER} mariadb -u root -p\"{DB_PASSWORD}\" {db_name} -e \"{escaped_command}\""
    try:
        result = subprocess.run(full_command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"SQL Error: {e.stderr}")
        return None

def setup_database():
    logging.info("Setting up the database...")
    
    if not os.path.exists(SQL_FILE):
        logging.error(f"SQL file not found: {SQL_FILE}")
        return False
    
    with open(SQL_FILE, 'r') as file:
        sql_content = file.read()
    
    # Split the SQL content into individual commands
    sql_commands = sql_content.split(';')
    
    for command in sql_commands:
        command = command.strip()
        if command:
            result = execute_sql(command, MARZBAN_DB)
            if result is None:
                logging.error(f"Failed to execute SQL command: {command[:50]}...")
                return False
    
    logging.info("Database setup completed successfully.")
    return True

def insert_usage_data():
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sql = f"CALL insert_current_usage('{current_time}');"
    result = execute_sql(sql)
    if result is not None:
        logging.info(f"Inserted usage snapshot at {current_time}")
    else:
        logging.error("Failed to insert usage snapshot")

def calculate_and_display_hourly_usage():
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sql = f"CALL calculate_hourly_usage('{current_time}');"
    result = execute_sql(sql)
    if result is not None:
        logging.info(f"Usage calculated at {current_time}:\n{result}")
    else:
        logging.error("Failed to calculate hourly usage")

def cleanup_old_data():
    sql = """
    DELETE FROM user_usage_snapshots WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 1 YEAR);
    DELETE FROM user_hourly_usage WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 1 YEAR);
    """
    result = execute_sql(sql)
    if result is not None:
        logging.info(f"Cleaned up data older than one year at {datetime.now()}")
    else:
        logging.error("Failed to clean up old data")

def should_run_cleanup():
    sql = "SELECT MAX(timestamp) FROM user_usage_snapshots;"
    result = execute_sql(sql)
    if result is not None:
        result = result.strip().split('\n')[-1]  # Get the last line
        if result.lower() == 'null' or result == '':
            return False  # No data to clean up
        try:
            last_snapshot = datetime.strptime(result, '%Y-%m-%d %H:%M:%S')
            return datetime.now() - last_snapshot > timedelta(days=365)  # Run cleanup annually
        except ValueError:
            logging.error(f"Unexpected date format: {result}")
            return False
    return False

def main():
    logging.info("Starting usage tracking system...")
    logging.info(f"Using database: user_usage_tracking on container: {DB_CONTAINER}")
    
    # Set up the database before starting the main loop
    if not setup_database():
        logging.error("Failed to set up the database. Exiting.")
        return
    
    last_insert = datetime.min
    last_cleanup_check = datetime.min
    
    try:
        while True:
            now = datetime.now()
            
            # Reload config to get the latest report_interval
            config = load_config()
            report_interval = config.get('report_interval', 60)  # Default to 60 minutes if not set
            
            # Insert usage data and calculate hourly usage every interval
            if now - last_insert >= timedelta(minutes=report_interval):
                insert_usage_data()
                calculate_and_display_hourly_usage()
                last_insert = now
            
            # Check for cleanup daily
            if now - last_cleanup_check >= timedelta(days=1):
                if should_run_cleanup():
                    cleanup_old_data()
                last_cleanup_check = now
            
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logging.info("Usage tracking system stopped.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
