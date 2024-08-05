import subprocess
import json
from datetime import datetime, timedelta
import pytz

CONFIG_FILE_PATH = "/opt/marzbackup/config.json"

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
        print(f"Inserted usage snapshot at {datetime.now(tehran_tz)}")
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
        print(f"Cleaned up data older than one year at {datetime.now(tehran_tz)}")
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
    if not is_within_schedule():
        print(f"Current time {datetime.now(tehran_tz)} is outside the scheduled execution window. Skipping execution.")
        return

    print(f"Running tasks at {datetime.now(tehran_tz)}")
    insert_usage_data()
    calculate_and_display_usage()
    if should_run_cleanup():
        cleanup_old_data()

if __name__ == "__main__":
    run_tasks()
