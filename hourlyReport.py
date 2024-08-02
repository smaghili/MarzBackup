import subprocess
import time
from datetime import datetime, timedelta
import json

def load_config():
    try:
        with open('/opt/marzbackup/config.json', 'r') as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        print("Config file not found. Using default values.")
        return {}
    except json.JSONDecodeError:
        print("Error decoding config file. Using default values.")
        return {}

config = load_config()

# Get backup interval from config, default to 60 minutes if not set
BACKUP_INTERVAL = config.get('backup_interval', 60)
if not isinstance(BACKUP_INTERVAL, int) or BACKUP_INTERVAL <= 0:
    BACKUP_INTERVAL = 60  # Default to 60 minutes if invalid value

print(f"Backup interval set to {BACKUP_INTERVAL} minutes")

def execute_sql(sql_command):
    full_command = f"docker exec -i marzban-db-1 mariadb -u root -p12341234 user_usage_tracking -e '{sql_command}'"
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

def calculate_and_display_hourly_usage():
    sql = "CALL calculate_hourly_usage();"
    result = execute_sql(sql)
    if result is not None:
        print(f"Usage in the last hour:\n{result}")
    else:
        print("Failed to calculate hourly usage")

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
    last_insert = datetime.min
    last_cleanup_check = datetime.min
    
    try:
        while True:
            now = datetime.now()
            
            # Insert usage data and calculate hourly usage every BACKUP_INTERVAL minutes
            if now - last_insert >= timedelta(minutes=BACKUP_INTERVAL):
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
