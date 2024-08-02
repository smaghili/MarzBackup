import subprocess
import time
import json
from datetime import datetime, timedelta
from config import load_config, CONFIG_FILE_PATH

def execute_sql(sql_command):
    config = load_config()
    db_container = config.get('db_container')
    db_password = config.get('db_password')
    db_name = config.get('db_name')
    db_type = config.get('db_type', 'mariadb')  # Default to mariadb if not specified
    
    full_command = f"docker exec -i {db_container} {db_type} -u root -p{db_password} {db_name} -e '{sql_command}'"
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
        print(f"Usage in the last interval:\n{result}")
    else:
        print("Failed to calculate usage")

def cleanup_old_data():
    sql = """
    DELETE FROM user_usage_snapshots WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 1 YEAR);
    DELETE FROM user_hourly_usage WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 1 YEAR);
    INSERT INTO cleanup_log (cleanup_time) VALUES (NOW());
    """
    result = execute_sql(sql)
    if result is not None:
        print(f"Cleaned up data older than one year at {datetime.now()}")
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
            return datetime.now() - last_cleanup > timedelta(days=365)  # Run cleanup annually
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
    config = load_config()
    db_name = config.get('db_name')
    db_container = config.get('db_container')
    print(f"Using database: {db_name} on container: {db_container}")
    
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
