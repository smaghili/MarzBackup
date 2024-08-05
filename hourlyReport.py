import subprocess
import json
from datetime import datetime, timedelta
import pytz
import traceback
import os

CONFIG_FILE_PATH = "/opt/marzbackup/config.json"
SQL_FILE_PATH = "/opt/MarzBackup/hourlyUsage.sql"  # Path to hourlyUsage.sql

def load_config():
    with open(CONFIG_FILE_PATH, 'r') as file:
        return json.load(file)

config = load_config()

DB_CONTAINER = config.get('db_container')
DB_PASSWORD = config.get('db_password')
REPORT_INTERVAL = config.get('report_interval', 60)  # Default to 60 minutes if not set

if not all([DB_CONTAINER, DB_PASSWORD]):
    raise ValueError("Missing database configuration in config file")

# Set Tehran timezone
tehran_tz = pytz.timezone('Asia/Tehran')

def execute_sql(sql_command):
    full_command = f"docker exec -i {DB_CONTAINER} mariadb -u root -p{DB_PASSWORD} UserUsageAnalytics -e \"{sql_command}\""
    try:
        result = subprocess.run(full_command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        print(f"Error output: {e.stderr}")
        print(f"SQL command that failed: {sql_command}")
        return None

def update_database_structure():
    if not os.path.exists(SQL_FILE_PATH):
        print(f"SQL file not found: {SQL_FILE_PATH}")
        return False

    with open(SQL_FILE_PATH, 'r') as sql_file:
        sql_content = sql_file.read()

    sql_statements = sql_content.split(';')

    for statement in sql_statements:
        if statement.strip():
            result = execute_sql(statement.strip() + ';')
            if result is None:
                print("Failed to execute SQL statement")
                return False
    print("Successfully updated database structure")
    return True

def insert_usage_data():
    now = datetime.now(tehran_tz)
    sql = f"CALL insert_current_usage('{now.strftime('%Y-%m-%d %H:%M:%S')}');"
    result = execute_sql(sql)
    if result is not None:
        print(f"Inserted usage snapshot at {now}")
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
    now = datetime.now(tehran_tz)
    sql = f"CALL cleanup_old_data('{now.strftime('%Y-%m-%d %H:%M:%S')}');"
    result = execute_sql(sql)
    if result is not None:
        print(f"Cleaned up data older than one year at {now}")
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
            last_cleanup = tehran_tz.localize(last_cleanup)
            return (datetime.now(tehran_tz) - last_cleanup).days >= 365  # Run cleanup annually
        except ValueError:
            print(f"Unexpected date format: {result}")
            return False
    return False

def is_within_schedule():
    now = datetime.now(tehran_tz)
    rounded_time = now.replace(minute=0, second=0, microsecond=0)
    if REPORT_INTERVAL < 60:
        rounded_time = now.replace(minute=(now.minute // REPORT_INTERVAL) * REPORT_INTERVAL, second=0, microsecond=0)
    return now - rounded_time < timedelta(minutes=1)

def run_tasks():
    now = datetime.now(tehran_tz)
    if not is_within_schedule():
        print(f"Current time {now} is outside the scheduled execution window. Skipping execution.")
        return

    print(f"Running tasks at {now}")
    try:
        if update_database_structure():
            insert_usage_data()
            calculate_and_display_usage()
            if should_run_cleanup():
                cleanup_old_data()
        else:
            print("Skipping tasks due to database structure update failure")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    run_tasks()
