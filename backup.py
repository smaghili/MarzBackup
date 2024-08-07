#!/usr/bin/env python3
import os
import sys
import fcntl
import logging
from datetime import datetime
import subprocess

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
    # Main backup process
    logging.info("Starting backup process")
    # Example: Run a shell command for backup
    result = subprocess.run(["/usr/bin/python3", "/opt/MarzBackup/backup_script.py"], capture_output=True, text=True)
    if result.returncode == 0:
        logging.info("Backup completed successfully")
    else:
        logging.error(f"Backup failed: {result.stderr}")

def main():
    if not acquire_lock():
        logging.info("Another instance is running. Exiting.")
        sys.exit(0)

    try:
        create_backup()
    except Exception as e:
        logging.exception("An error occurred during backup")
    finally:
        release_lock()

if __name__ == "__main__":
    main()
