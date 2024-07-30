#!/bin/bash

INSTALL_DIR="/opt/MarzBackup"
REPO_URL="https://github.com/smaghili/MarzBackup.git"
CONFIG_DIR="/opt/marzbackup"

update() {
    echo "Updating MarzBackup..."
    if [ -d "$INSTALL_DIR" ]; then
        cd "$INSTALL_DIR"
        git fetch origin
        git reset --hard origin/main
        pip3 install -r requirements.txt
        echo "Update completed successfully."
    else
        echo "MarzBackup is not installed. Please install it first."
        exit 1
    fi
}

start() {
    echo "Starting MarzBackup..."
    if [ -d "$INSTALL_DIR" ]; then
        cd "$INSTALL_DIR"
        python3 main.py
    else
        echo "MarzBackup is not installed. Please install it first."
        exit 1
    fi
}

case "$1" in
    update)
        update
        ;;
    start)
        start
        ;;
    *)
        echo "Usage: marzbackup {update|start}"
        exit 1
        ;;
esac

exit 0
