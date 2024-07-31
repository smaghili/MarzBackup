#!/bin/bash

REPO_URL="https://github.com/smaghili/MarzBackup.git"
SCRIPT_PATH="/usr/local/bin/marzbackup"
TEMP_SCRIPT="/tmp/marzbackup_new.sh"
INSTALL_DIR="/opt/MarzBackup"
CONFIG_DIR="/opt/marzbackup"
LOG_FILE="/var/log/marzbackup.log"
PID_FILE="/var/run/marzbackup.pid"

update() {
    echo "Updating MarzBackup..."
    stop
    if [ -d "$INSTALL_DIR" ]; then
        cd "$INSTALL_DIR"
        git fetch origin
        git reset --hard origin/main
        pip3 install -r requirements.txt
        
        # Update marzbackup.sh
        if [ -f "$INSTALL_DIR/marzbackup.sh" ]; then
            sudo cp "$INSTALL_DIR/marzbackup.sh" "$TEMP_SCRIPT"
            sudo chmod +x "$TEMP_SCRIPT"
            echo "New version of marzbackup.sh downloaded. Applying update..."
            sudo mv "$TEMP_SCRIPT" "$SCRIPT_PATH"
            echo "marzbackup.sh has been updated. Restarting with new version..."
            exec "$SCRIPT_PATH" start
        else
            echo "Error: marzbackup.sh not found in repository."
            exit 1
        fi
    else
        echo "MarzBackup is not installed. Please install it first."
        exit 1
    fi
}

start() {
    echo "Starting MarzBackup..."
    if [ -d "$INSTALL_DIR" ]; then
        cd "$INSTALL_DIR"
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p $PID > /dev/null; then
                echo "MarzBackup is already running. Use 'marzbackup restart' to restart it."
                return
            else
                echo "Stale PID file found. Removing it."
                rm "$PID_FILE"
            fi
        fi
        nohup python3 main.py > "$LOG_FILE" 2>&1 & echo $! > "$PID_FILE"
        sleep 5  # Give more time for the bot to start and send the welcome message
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p $PID > /dev/null; then
                echo "Bot is running in the background. PID: $PID"
                echo "You can check its status with 'marzbackup status'."
                echo "To view logs, use: tail -f $LOG_FILE"
            else
                echo "Failed to start the bot. Check logs for details."
                cat "$LOG_FILE"
            fi
        else
            echo "Failed to start the bot. PID file not created."
            cat "$LOG_FILE"
        fi
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
        if ps -p $PID > /dev/null; then
            echo "MarzBackup is running. PID: $PID"
            echo "Last 10 lines of log:"
            tail -n 10 "$LOG_FILE"
        else
            echo "MarzBackup is not running, but PID file exists. It may have crashed."
            echo "Last 20 lines of log:"
            tail -n 20 "$LOG_FILE"
            rm "$PID_FILE"
        fi
    else
        echo "MarzBackup is not running."
        if [ -f "$LOG_FILE" ]; then
            echo "Last 20 lines of log:"
            tail -n 20 "$LOG_FILE"
        else
            echo "No log file found."
        fi
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
