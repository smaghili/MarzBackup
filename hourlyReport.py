import subprocess
import time
import json
import os
from datetime import datetime, timedelta

CONFIG_FILE_PATH = "/opt/marzbackup/config.json"

def load_config():
    with open(CONFIG_FILE_PATH, 'r') as file:
        return json.load(file)

config = load_config()

DB_CONTAINER = config.get('db_container')
DB_PASSWORD = config.get('db_password')

if not all([DB_CONTAINER, DB_PASSWORD]):
    raise ValueError("Missing database configuration in config file")

def execute_sql(sql_command):
    full_command = f"docker exec -i {DB_CONTAINER} mariadb -u root -p{DB_PASSWORD} UserUsageAnalytics -e '{sql_command}'"
    try:
        result = subprocess.run(full_command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        print(f"Error output: {e.stderr}")
        return None

def insert_usage_data():
    sql = "CALL insert_current_usage();"
    result = execute_sql(sql)
    if result is not None:
        print(f"Inserted usage snapshot at {datetime.now()}")
    else:
        print("Failed to insert usage snapshot")

def calculate_and_display_usage():
    sql = "CALL calculate_usage();"
    result = execute_sql(sql)
    if result is not None:
        print(f"Usage in the last period:")
        # Parse and format the result
        lines = result.strip().split('\n')[1:]  # Skip the header
        for line in lines:
            user_id, username, usage, timestamp, report_number = line.split('\t')
            print(f"user_id: {user_id}, username: {username}, usage_in_period: {usage}, timestamp: {timestamp}, report_number: {report_number}")
    else:
        print("Failed to calculate usage")

def check_usage_data():
    sql = "CALL check_usage_data();"
    result = execute_sql(sql)
    if result is not None:
        print("Usage data check:")
        print(result)
    else:
        print("Failed to check usage data")

def cleanup_old_data():
    sql = "CALL cleanup_old_data();"
    result = execute_sql(sql)
    if result is not None:
        print(f"Cleaned up old data at {datetime.now()}")
    else:
        print("Failed to clean up old data")

def main():
    print("Starting usage tracking system...")
    print(f"Using database on container: {DB_CONTAINER}")
    
    last_insert = datetime.min
    last_cleanup_check = datetime.min
    
    try:
        while True:
            now = datetime.now()
            
            # Reload config to get the latest report_interval
            config = load_config()
            report_interval = config.get('report_interval', 60)  # Default to 60 minutes if not set
            
            # Insert usage data and calculate usage every interval
            if now - last_insert >= timedelta(minutes=report_interval):
                insert_usage_data()
                calculate_and_display_usage()
                check_usage_data()
                last_insert = now
            
            # Check for cleanup daily
            if now - last_cleanup_check >= timedelta(days=1):
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
