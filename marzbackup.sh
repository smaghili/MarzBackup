#!/bin/bash

INSTALL_DIR="/opt/MarzBackup"
REPO_URL="https://github.com/smaghili/MarzBackup.git"
CONFIG_DIR="/opt/marzbackup"
LOG_FILE="/var/log/marzbackup.log"
PID_FILE="/var/run/marzbackup.pid"

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
        nohup python3 main.py > "$LOG_FILE" 2>&1 & echo $! > "$PID_FILE"
        echo "Bot is running in the background. You can check its status with 'marzbackup status'."
        echo "To view logs, use: tail -f $LOG_FILE"
    else
        echo "MarzBackup is not installed. Please install it first."
        exit 1
    fi
}

stop() {
    echo "Stopping MarzBackup..."
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        kill $PID
        rm "$PID_FILE"
        echo "MarzBackup stopped."
    else
        echo "MarzBackup is not running or PID file not found."
    fi
}

restart() {
    stop
    sleep 2
    start
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null
        then
            echo "MarzBackup is running. PID: $PID"
        else
            echo "MarzBackup is not running, but PID file exists. It may have crashed."
            rm "$PID_FILE"
        fi
    else
        echo "MarzBackup is not running."
    fi
}

case "$1" in
    update)
        update
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: marzbackup {update|start|stop|restart|status}"
        exit 1
        ;;
esac

exit 0
