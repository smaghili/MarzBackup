import subprocess
import time
import json
import os
import logging
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
CONFIG_FILE = '/opt/marzbackup/config.json'
SQL_FILE = '/opt/MarzBackup/hourlyUsage.sql'

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as file:
            config = json.load(file)
        return config
    except FileNotFoundError:
        logging.error(f"Config file not found: {CONFIG_FILE}")
        return {}
    except json.JSONDecodeError:
        logging.error(f"Error decoding config file: {CONFIG_FILE}")
        return {}

config = load_config()

# Database configuration
DB_CONTAINER = config.get('db_container', 'marzban-db-1')
DB_PASSWORD = config.get('db_password', '12341234')
DB_TYPE = config.get('db_type', 'mariadb')
MARZBAN_DB = config.get('marzban_db', 'marzban')
USER_TRACKING_DB = 'user_usage_tracking'

# Get report interval from config, default to 60 minutes if not set
REPORT_INTERVAL = config.get('report_interval', 60)
if not isinstance(REPORT_INTERVAL, int) or REPORT_INTERVAL <= 0:
    REPORT_INTERVAL = 60

logging.info(f"Report interval set to {REPORT_INTERVAL} minutes")

def execute_sql(sql_command, db_name=None):
    if db_name is None:
        db_name = USER_TRACKING_DB
    
    try:
        escaped_sql = sql_command.replace("'", "'\\''").replace('"', '\\"')
        command = f"docker exec -i {DB_CONTAINER} {DB_TYPE} -u root -p{DB_PASSWORD} {db_name} -e \"{escaped_sql}\""
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"SQL execution error: {e}")
        logging.error(f"Error output: {e.stderr}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in execute_sql: {e}")
        return None

def setup_database():
    logging.info("Setting up the user tracking database...")
    
    if not os.path.exists(SQL_FILE):
        logging.error(f"SQL file not found: {SQL_FILE}")
        return False
    
    with open(SQL_FILE, 'r') as file:
        sql_content = file.read()
    
    # Split SQL content into individual statements
    statements = sql_content.split(';')
    
    for statement in statements:
        statement = statement.strip()
        if statement:
            result = execute_sql(statement)
            if result is None:
                logging.error(f"Failed to execute SQL statement: {statement[:50]}...")
                return False
    
    logging.info("User tracking database setup completed successfully.")
    return True

def get_user_data():
    query = f"SELECT id, username, used_traffic FROM {MARZBAN_DB}.users;"
    return execute_sql(query, MARZBAN_DB)

def insert_usage_data():
    user_data = get_user_data()
    if user_data is None:
        logging.error("Failed to retrieve user data from Marzban database.")
        return

    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for line in user_data.split('\n')[1:]:  # Skip header row
        user_id, username, used_traffic = line.split('\t')
        sql = f"INSERT INTO user_usage_snapshots (user_id, timestamp, total_usage) VALUES ({user_id}, '{current_time}', {used_traffic});"
        result = execute_sql(sql)
        if result is None:
            logging.error(f"Failed to insert usage data for user {username}")
    
    logging.info(f"Inserted usage snapshot at {current_time}")

def calculate_and_display_hourly_usage():
    sql = "CALL calculate_hourly_usage();"
    result = execute_sql(sql)
    if result is not None:
        logging.info(f"Usage calculated:\n{result}")
    else:
        logging.error("Failed to calculate hourly usage")

def cleanup_old_data():
    sql = "CALL cleanup_old_data();"
    result = execute_sql(sql)
    if result is not None:
        logging.info(f"Cleaned up old data at {datetime.now()}")
    else:
        logging.error("Failed to clean up old data")

def should_run_cleanup():
    sql = "SELECT MAX(timestamp) FROM user_usage_snapshots;"
    result = execute_sql(sql)
    if result and result.lower() != 'null' and result != '':
        try:
            last_snapshot = datetime.strptime(result, '%Y-%m-%d %H:%M:%S')
            return datetime.now() - last_snapshot > timedelta(days=60)
        except ValueError:
            logging.error(f"Unexpected date format: {result}")
    return False

def main():
    logging.info("Starting usage tracking system...")
    
    if not setup_database():
        logging.error("Failed to set up the database. Exiting.")
        return
    
    last_insert = datetime.min
    last_cleanup_check = datetime.min
    
    try:
        while True:
            now = datetime.now()
            
            if now - last_insert >= timedelta(minutes=REPORT_INTERVAL):
                insert_usage_data()
                calculate_and_display_hourly_usage()
                last_insert = now
            
            if now - last_cleanup_check >= timedelta(days=1):
                if should_run_cleanup():
                    cleanup_old_data()
                last_cleanup_check = now
            
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logging.info("Usage tracking system stopped.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main()
