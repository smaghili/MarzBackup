import subprocess
import time
import json
import os
from datetime import datetime, timedelta
import schedule

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
        print(f"Usage in the last period:\n{result}")
    else:
        print("Failed to calculate usage")

def cleanup_old_data():
    sql = """
    DELETE FROM UsageSnapshots WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 1 YEAR);
    DELETE FROM PeriodicUsage WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 1 YEAR);
    INSERT INTO CleanupLog (cleanup_time) VALUES (NOW());
    """
    result = execute_sql(sql)
    if result is not None:
        print(f"Cleaned up data older than one year at {datetime.now()}")
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
            return datetime.now() - last_cleanup > timedelta(days=365)  # Run cleanup annually
        except ValueError:
            print(f"Unexpected date format: {result}")
            return False
    return False

def get_historical_hourly_usage(start_time, end_time):
    sql = f"CALL get_historical_usage('{start_time}', '{end_time}');"
    result = execute_sql(sql)
    if result is not None:
        print(f"Historical usage between {start_time} and {end_time}:\n{result}")
    else:
        print("Failed to get historical usage")

def main():
    print("Starting usage tracking system...")
    print(f"Using database on container: {DB_CONTAINER}")
    
    # Schedule tasks
    config = load_config()
    report_interval = config.get('report_interval', 5)  # Default to 5 minutes if not set
    
    schedule.every(report_interval).minutes.do(insert_usage_data)
    schedule.every(report_interval).minutes.do(calculate_and_display_usage)
    schedule.every().day.at("00:00").do(lambda: should_run_cleanup() and cleanup_old_data())
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("Usage tracking system stopped.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise

if __name__ == "__main__":
    main()
