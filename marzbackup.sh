#!/bin/bash

REPO_URL="https://github.com/smaghili/MarzBackup.git"
SCRIPT_PATH="/usr/local/bin/marzbackup"
TEMP_SCRIPT="/tmp/marzbackup_new.sh"
INSTALL_DIR="/opt/MarzBackup"
CONFIG_DIR="/opt/marzbackup"
LOG_FILE="/var/log/marzbackup.log"
PID_FILE="/var/run/marzbackup.pid"
VERSION_FILE="$CONFIG_DIR/version.json"

get_current_version() {
    if [ -f "$VERSION_FILE" ]; then
        version=$(grep -o '"installed_version": "[^"]*' "$VERSION_FILE" | grep -o '[^"]*$')
        echo $version
    else
        echo "stable"  # Default to stable if version file doesn't exist
    fi
}

update() {
    echo "Checking for updates..."
    current_version=$(get_current_version)
    
    if [ "$2" == "dev" ]; then
        BRANCH="dev"
        NEW_VERSION="dev"
    elif [ "$2" == "stable" ]; then
        BRANCH="main"
        NEW_VERSION="stable"
    elif [ -z "$2" ]; then
        BRANCH=$([ "$current_version" == "dev" ] && echo "dev" || echo "main")
        NEW_VERSION=$current_version
    else
        echo "Invalid version specified. Use 'dev' or 'stable'."
        exit 1
    fi

    if [ -d "$INSTALL_DIR" ]; then
        cd "$INSTALL_DIR"
        git fetch origin
        git checkout $BRANCH
        LOCAL=$(git rev-parse HEAD)
        REMOTE=$(git rev-parse @{u})

        if [ "$LOCAL" = "$REMOTE" ] && [ "$NEW_VERSION" == "$current_version" ]; then
            echo "You are already using the latest $NEW_VERSION version."
            exit 0
        else
            echo "Updating MarzBackup to $NEW_VERSION version..."
            stop
            git reset --hard origin/$BRANCH
            pip3 install -r requirements.txt
            
            # Update marzbackup.sh
            if [ -f "$INSTALL_DIR/marzbackup.sh" ]; then
                sudo cp "$INSTALL_DIR/marzbackup.sh" "$TEMP_SCRIPT"
                sudo chmod +x "$TEMP_SCRIPT"
                echo "New version of marzbackup.sh downloaded. Applying update..."
                sudo mv "$TEMP_SCRIPT" "$SCRIPT_PATH"
                echo "{\"installed_version\": \"$NEW_VERSION\"}" > "$VERSION_FILE"
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
        sleep 2
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

install_user_usage() {
    echo "Installing user usage tracking system..."
    
    # Copy SQL and Python files to the installation directory
    sudo cp "$INSTALL_DIR/hourlyUsage.sql" "$INSTALL_DIR/"
    sudo cp "$INSTALL_DIR/hourlyReport.py" "$INSTALL_DIR/"
    
    # Load config (this function was previously implemented and includes checking and updating information)
    python3 "$INSTALL_DIR/config.py"
    
    # Execute SQL script
    echo "Setting up database structures..."
    db_container=$(python3 -c "from config import DB_CONTAINER; print(DB_CONTAINER)")
    db_password=$(python3 -c "from config import DB_PASSWORD; print(DB_PASSWORD)")
    db_name=$(python3 -c "from config import DB_NAME; print(DB_NAME)")
    docker exec -i "$db_container" mariadb -u root -p"$db_password" < "$INSTALL_DIR/hourlyUsage.sql"
    
    # Install required Python packages
    echo "Installing required Python packages..."
    pip3 install subprocess
    
    # Start hourly report script
    echo "Starting hourly report script..."
    nohup python3 "$INSTALL_DIR/hourlyReport.py" > "$LOG_FILE" 2>&1 &
    
    echo "User usage tracking system installed and started."
}

case "$1" in
    update)
        update $@
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
    install-user-usage)
        install_user_usage
        ;;
    *)
        echo "Usage: marzbackup {update [dev|stable]|start|stop|restart|status|install-user-usage}"
        exit 1
        ;;
esac

exit 0
