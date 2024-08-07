#!/usr/bin/env python3
import os
import sys
import fcntl
import logging
from datetime import datetime
import subprocess
from config import load_config

# Logging configuration
logging.basicConfig(filename='/var/log/marzbackup.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Lock file path
LOCK_FILE = '/tmp/marzbackup.lock'

def acquire_lock():
    global lock_file
    try:
        lock_file = open(LOCK_FILE, 'w')
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except IOError:
        return False

def release_lock():
    global lock_file
    fcntl.lockf(lock_file, fcntl.LOCK_UN)
    lock_file.close()
    os.remove(LOCK_FILE)

def create_backup():
    logging.info("Starting backup process")
    config = load_config()
    
    # Extract database information from config
    db_container = config.get("db_container")
    db_password = config.get("db_password")
    db_name = config.get("db_name")
    
    if not db_container or not db_password or not db_name:
        logging.error("Database information not found in config file.")
        return False
    
    # Create backup directory if it doesn't exist
    backup_dir = "/var/lib/marzban/mysql/db-backup"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Generate backup file name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{backup_dir}/backup_{timestamp}.sql"
    
    # Create backup
    backup_command = f"docker exec {db_container} mysqldump -u root -p{db_password} {db_name} > {backup_file}"
    result = subprocess.run(backup_command, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        logging.info(f"Backup created successfully: {backup_file}")
        return True
    else:
        logging.error(f"Backup failed: {result.stderr}")
        return False

def main():
    if not acquire_lock():
        logging.info("Another instance is running. Exiting.")
        sys.exit(0)

    try:
        success = create_backup()
        if success:
            logging.info("Backup process completed successfully")
        else:
            logging.error("Backup process failed")
    except Exception as e:
        logging.exception("An error occurred during backup")
    finally:
        release_lock()

if __name__ == "__main__":
    main()
