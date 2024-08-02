import subprocess
import time
import json
import os
from datetime import datetime, timedelta
from config import load_config, CONFIG_FILE_PATH

INSTALL_DIR = "/opt/MarzBackup"
SQL_FILE = os.path.join(INSTALL_DIR, 'hourlyUsage.sql')

def load_config():
    with open(CONFIG_FILE_PATH, 'r') as file:
        return json.load(file)

config = load_config()

DB_CONTAINER = config.get('db_container')
DB_PASSWORD = config.get('db_password')
DB_NAME = config.get('db_name')

if not all([DB_CONTAINER, DB_PASSWORD, DB_NAME]):
    raise ValueError("Missing database configuration in config file")

def execute_sql(sql_command, db_name='user_usage_tracking'):
    escaped_command = sql_command.replace("'", "'\\''").replace('"', '\\"')
    full_command = f'docker exec -i {DB_CONTAINER} bash -c "mariadb -u root -p\'{DB_PASSWORD}\' {db_name} -e \"{escaped_command}\""'
    try:
        result = subprocess.run(full_command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        print(f"Error output: {e.stderr}")
        return None

def setup_database():
    if not os.path.exists(SQL_FILE):
        raise FileNotFoundError(f"SQL file not found: {SQL_FILE}")
    
    print("Setting up the database...")
    
    # Create the database if it doesn't exist
    create_db_command = "CREATE DATABASE IF NOT EXISTS user_usage_tracking;"
    result = execute_sql(create_db_command, DB_NAME)
    if result is None:
        print("Failed to create database.")
        return False
    
    # Execute the SQL commands to create tables and procedures
    sql_commands = [
        """
        CREATE TABLE IF NOT EXISTS user_usage_snapshots (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            timestamp DATETIME NOT NULL,
            total_usage BIGINT NOT NULL,
            INDEX idx_user_timestamp (user_id, timestamp)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS user_hourly_usage (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            username VARCHAR(255) NOT NULL,
            usage_in_last_hour BIGINT NOT NULL,
            timestamp DATETIME NOT NULL,
            INDEX idx_user_timestamp (user_id, timestamp)
        );
        """,
        """
        CREATE OR REPLACE PROCEDURE insert_current_usage(IN current_timestamp DATETIME)
        BEGIN
            INSERT INTO user_usage_snapshots (user_id, timestamp, total_usage)
            SELECT id, current_timestamp, COALESCE(used_traffic, 0)
            FROM marzban.users;
        END
        """,
        """
        CREATE OR REPLACE PROCEDURE calculate_hourly_usage(IN current_timestamp DATETIME)
        BEGIN
            INSERT INTO user_hourly_usage (user_id, username, usage_in_last_hour, timestamp)
            SELECT 
                u.id AS user_id,
                u.username,
                COALESCE(new.total_usage - old.total_usage, 0) AS usage_in_last_hour,
                current_timestamp AS timestamp
            FROM 
                marzban.users u
            LEFT JOIN user_usage_snapshots new ON u.id = new.user_id AND new.timestamp = (
                SELECT MAX(timestamp) FROM user_usage_snapshots WHERE user_id = u.id
            )
            LEFT JOIN user_usage_snapshots old ON u.id = old.user_id AND old.timestamp = (
                SELECT MAX(timestamp) FROM user_usage_snapshots 
                WHERE user_id = u.id AND timestamp < new.timestamp
            )
            WHERE
                new.timestamp > DATE_SUB(current_timestamp, INTERVAL 1 HOUR);

            SELECT user_id, username, usage_in_last_hour, timestamp
            FROM user_hourly_usage
            WHERE timestamp = current_timestamp;
        END
        """
    ]
    
    for command in sql_commands:
        result = execute_sql(command)
        if result is None:
            print(f"Failed to execute SQL command: {command[:50]}...")
            return False
    
    print("Database setup completed successfully.")
    return True

def insert_usage_data():
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sql = f"CALL insert_current_usage('{current_time}');"
    result = execute_sql(sql)
    if result is not None:
        print(f"Inserted usage snapshot at {current_time}")
    else:
        print("Failed to insert usage snapshot")

def calculate_and_display_hourly_usage():
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sql = f"CALL calculate_hourly_usage('{current_time}');"
    result = execute_sql(sql)
    if result is not None:
        print(f"Usage calculated at {current_time}:\n{result}")
    else:
        print("Failed to calculate hourly usage")

def cleanup_old_data():
    sql = """
    DELETE FROM user_usage_snapshots WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 1 YEAR);
    DELETE FROM user_hourly_usage WHERE timestamp < DATE_SUB(CURDATE(), INTERVAL 1 YEAR);
    """
    result = execute_sql(sql)
    if result is not None:
        print(f"Cleaned up data older than one year at {datetime.now()}")
    else:
        print("Failed to clean up old data")

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
            print(f"Unexpected date format: {result}")
            return False
    return False

def main():
    print("Starting usage tracking system...")
    print(f"Using database: user_usage_tracking on container: {DB_CONTAINER}")
    
    # Set up the database before starting the main loop
    if not setup_database():
        print("Failed to set up the database. Exiting.")
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
        print("Usage tracking system stopped.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise

if __name__ == "__main__":
    main()
