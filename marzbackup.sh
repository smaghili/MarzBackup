#!/bin/bash

REPO_URL="https://github.com/smaghili/MarzBackup.git"
SCRIPT_PATH="/usr/local/bin/marzbackup"
TEMP_SCRIPT="/tmp/marzbackup_new.sh"

# Load user configurations
CONFIG_FILE="/etc/marzbackup/config.sh"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    echo "Config file not found. Using default settings."
    INSTALL_DIR="/opt/MarzBackup"
    CONFIG_DIR="/opt/marzbackup"
    LOG_FILE="/var/log/marzbackup.log"
    PID_FILE="/var/run/marzbackup.pid"
fi

update() {
    echo "Updating MarzBackup..."
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
            exec "$SCRIPT_PATH" update_finalize
        else
            echo "Error: marzbackup.sh not found in repository."
            exit 1
        fi
    else
        echo "MarzBackup is not installed. Please install it first."
        exit 1
    fi
}

update_finalize() {
    echo "Finalizing update..."
    
    # Ensure config file exists and is not overwritten
    if [ ! -f "$CONFIG_FILE" ]; then
        sudo mkdir -p $(dirname "$CONFIG_FILE")
        sudo cp "$INSTALL_DIR/config.sh" "$CONFIG_FILE"
    fi
    
    echo "Update completed successfully."
    
    # Restart the service to apply changes
    restart
}

start() {
    echo "Starting MarzBackup..."
    if [ -d "$INSTALL_DIR" ]; then
        cd "$INSTALL_DIR"
        if [ -f "$PID_FILE" ]; then
            echo "MarzBackup is already running. Use 'marzbackup restart' to restart it."
        else
            nohup python3 main.py > "$LOG_FILE" 2>&1 & echo $! > "$PID_FILE"
            echo "Bot is running in the background. You can check its status with 'marzbackup status'."
            echo "To view logs, use: tail -f $LOG_FILE"
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
    update_finalize)
        update_finalize
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
