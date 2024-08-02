import subprocess
import time
import json
import os
from datetime import datetime, timedelta

# Constants
CONFIG_FILE = '/opt/marzbackup/config.json'
SQL_FILE = '/opt/MarzBackup/hourlyUsage.sql'

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        print(f"Config file not found: {CONFIG_FILE}")
        return {}
    except json.JSONDecodeError:
        print(f"Error decoding config file: {CONFIG_FILE}")
        return {}

config = load_config()

# Database configuration
DB_CONTAINER = config.get('db_container', 'marzban-db-1')
DB_PASSWORD = config.get('db_password', '12341234')
DB_TYPE = config.get('db_type', 'mariadb')
USAGE_DB = 'UserUsageAnalytics'

# Get report interval from config, default to 60 minutes if not set
REPORT_INTERVAL = config.get('report_interval', 60)
if not isinstance(REPORT_INTERVAL, int) or REPORT_INTERVAL <= 0:
    REPORT_INTERVAL = 60

print(f"Report interval set to {REPORT_INTERVAL} minutes")

def execute_sql(sql_command):
    full_command = f"docker exec -i {DB_CONTAINER} {DB_TYPE} -u root -p{DB_PASSWORD} {USAGE_DB} -e '{sql_command}'"
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
    
    full_command = f"docker exec -i {DB_CONTAINER} {DB_TYPE} -u root -p{DB_PASSWORD} < {SQL_FILE}"
    try:
        subprocess.run(full_command, shell=True, check=True)
        print("Database setup completed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to execute SQL file. Error: {e}")
        return False

def insert_usage_data():
    sql = "CALL InsertCurrentUsage();"
    result = execute_sql(sql)
    if result is not None:
        print(f"Inserted usage snapshot at {datetime.now()}")
    else:
        print("Failed to insert usage snapshot")

def calculate_and_display_usage():
    sql = "CALL CalculateUsage();"
    result = execute_sql(sql)
    if result is not None:
        print(f"Usage in the last {REPORT_INTERVAL} minutes:\n{result}")
    else:
        print(f"Failed to calculate usage for the last {REPORT_INTERVAL} minutes")

def cleanup_old_data():
    sql = "CALL CleanupOldData();"
    result = execute_sql(sql)
    if result is not None:
        print(f"Cleaned up old data at {datetime.now()}")
    else:
        print("Failed to clean up old data")

def should_run_cleanup():
    sql = "SELECT MAX(cleanup_time) FROM CleanupLog;"
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

def get_historical_usage(start_time, end_time):
    sql = f"CALL GetHistoricalUsage('{start_time}', '{end_time}');"
    result = execute_sql(sql)
    if result is not None:
        print(f"Historical usage between {start_time} and {end_time}:\n{result}")
    else:
        print("Failed to get historical usage")

def main():
    print("Starting usage tracking system...")
    
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
                calculate_and_display_usage()
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
