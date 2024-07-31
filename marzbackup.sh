#!/bin/bash

REPO_URL="https://github.com/smaghili/MarzBackup.git"
SCRIPT_PATH="/usr/local/bin/marzbackup"
TEMP_SCRIPT="/tmp/marzbackup_new.sh"
INSTALL_DIR="/opt/MarzBackup"
CONFIG_DIR="/opt/marzbackup"
LOG_FILE="/var/log/marzbackup.log"
PID_FILE="/var/run/marzbackup.pid"

update() {
    echo "Checking for updates..."
    if [ -d "$INSTALL_DIR" ]; then
        cd "$INSTALL_DIR"
        git fetch origin
        LOCAL=$(git rev-parse HEAD)
        REMOTE=$(git rev-parse @{u})

        if [ "$LOCAL" = "$REMOTE" ]; then
            echo "You are already using the latest version."
            exit 0
        else
            echo "Updating MarzBackup..."
            stop
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
        fi
    else
        echo "MarzBackup is not installed. Please install it first."
        exit 1
    fi
}

# ... (rest of the script remains unchanged)

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
