import subprocess
import time
import json
import os
from datetime import datetime, timedelta

INSTALL_DIR = "/opt/MarzBackup"
SQL_FILE = os.path.join(INSTALL_DIR, 'hourlyUsage.sql')

# Load configuration from config.json
def load_config():
    with open('/opt/marzbackup/config.json', 'r') as config_file:
        return json.load(config_file)

config = load_config()

# Extract database information from config
DB_CONTAINER = config.get('db_container', 'marzban-db-1')
DB_PASSWORD = config.get('db_password', '12341234')
DB_TYPE = config.get('db_type', 'mariadb')

# Get report interval from config, default to 60 minutes (1 hour) if not set
REPORT_INTERVAL = config.get('report_interval')
if REPORT_INTERVAL is None or not isinstance(REPORT_INTERVAL, int) or REPORT_INTERVAL <= 0:
    REPORT_INTERVAL = 60  # Default to 60 minutes (1 hour)

print(f"Report interval set to {REPORT_INTERVAL} minutes")

def execute_sql(sql_command, db_name=None):
    if db_name is None:
        db_name = 'user_usage_tracking'
    full_command = f"docker exec -i {DB_CONTAINER} {DB_TYPE} -u root -p{DB_PASSWORD} {db_name} -e '{sql_command}'"
    try:
        result = subprocess.run(full_command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        print(f"Error output: {e.stderr}")
        return None

def setup_database():
    print("Setting up the database...")
    
    if not os.path.exists(SQL_FILE):
        print(f"SQL file not found: {SQL_FILE}")
        return False
    
    with open(SQL_FILE, 'r') as file:
        sql_content = file.read()
    
    # Create the database if it doesn't exist
    create_db_command = "CREATE DATABASE IF NOT EXISTS user_usage_tracking;"
    result = execute_sql(create_db_command, 'mysql')
    if result is None:
        print("Failed to create database.")
        return False
    
    # Execute the SQL file content
    result = execute_sql(sql_content)
    if result is None:
        print("Failed to execute SQL file content.")
        return False
    
    print("Database setup completed successfully.")
    return True

def insert_usage_data():
    sql = "CALL insert_current_usage();"
    result = execute_sql(sql)
    if result is not None:
        print(f"Inserted usage snapshot at {datetime.now()}")
    else:
        print("Failed to insert usage snapshot")

def calculate_and_display_hourly_usage():
    sql = "CALL calculate_hourly_usage();"
    result = execute_sql(sql)
    if result is not None:
        print(f"Usage in the last {REPORT_INTERVAL} minutes:\n{result}")
    else:
        print(f"Failed to calculate usage for the last {REPORT_INTERVAL} minutes")

def cleanup_old_data():
    sql = "CALL cleanup_old_data();"
    result = execute_sql(sql)
    if result is not None:
        print(f"Cleaned up old data at {datetime.now()}")
    else:
        print("Failed to clean up old data")

def should_run_cleanup():
    sql = "SELECT MAX(cleanup_time) FROM cleanup_log;"
    result = execute_sql(sql)
    if result is not None:
        result = result.strip().split('\n')[-1]  # Get the last line
        if result.lower() == 'null' or result == '':
            return True  # If no cleanup has been done, we should run it
        try:
            last_cleanup = datetime.strptime(result, '%Y-%m-%d %H:%M:%S')
            return datetime.now() - last_cleanup > timedelta(days=60)
        except ValueError:
            print(f"Unexpected date format: {result}")
            return False
    return False

def get_historical_hourly_usage(start_time, end_time):
    sql = f"CALL get_historical_hourly_usage('{start_time}', '{end_time}');"
    result = execute_sql(sql)
    if result is not None:
        print(f"Historical hourly usage between {start_time} and {end_time}:\n{result}")
    else:
        print("Failed to get historical hourly usage")

def main():
    print("Starting usage tracking system...")
    
    # Set up the database before starting the main loop
    if not setup_database():
        print("Failed to set up the database. Exiting.")
        return
    
    last_insert = datetime.min
    last_cleanup_check = datetime.min
    
    try:
        while True:
            now = datetime.now()
            
            # Insert usage data and calculate usage every REPORT_INTERVAL minutes
            if now - last_insert >= timedelta(minutes=REPORT_INTERVAL):
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
        print("Usage tracking system stopped.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise

if __name__ == "__main__":
    main()

# Uncomment and modify these lines to test specific functionalities
# get_historical_hourly_usage(datetime.now() - timedelta(days=7), datetime.now())
