#!/bin/bash

REPO_URL="https://github.com/smaghili/MarzBackup.git"
SCRIPT_PATH="/usr/local/bin/marzbackup"
TEMP_SCRIPT="/tmp/marzbackup_new.sh"
INSTALL_DIR="/opt/MarzBackup"
CONFIG_DIR="/opt/marzbackup"
LOG_FILE="/var/log/marzbackup.log"
PID_FILE="/var/run/marzbackup.pid"
VERSION_FILE="$CONFIG_DIR/version.json"
CONFIG_FILE="$CONFIG_DIR/config.json"
USAGE_PID_FILE="/var/run/marzbackup_usage.pid"

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
    echo "Checking user usage tracking system..."
    
    if [ -f "$USAGE_PID_FILE" ]; then
        PID=$(cat "$USAGE_PID_FILE")
        if ps -p $PID > /dev/null; then
            echo "User usage tracking system is already running."
            return
        else
            echo "Stale PID file found. Removing it."
            rm "$USAGE_PID_FILE"
        fi
    fi
    
    echo "Installing user usage tracking system..."
    
    # Check if jq is installed
    if ! command -v jq &> /dev/null; then
        echo "jq is not installed. Installing jq..."
        sudo apt-get update && sudo apt-get install -y jq
    fi
    
    # Check and copy SQL and Python files if needed
    if [ ! -f "$INSTALL_DIR/hourlyUsage.sql" ]; then
        echo "Copying hourlyUsage.sql to installation directory..."
        sudo cp "$INSTALL_DIR/hourlyUsage.sql" "$INSTALL_DIR/"
    else
        echo "hourlyUsage.sql already exists in the installation directory."
    fi

    if [ ! -f "$INSTALL_DIR/hourlyReport.py" ]; then
        echo "Copying hourlyReport.py to installation directory..."
        sudo cp "$INSTALL_DIR/hourlyReport.py" "$INSTALL_DIR/"
    else
        echo "hourlyReport.py already exists in the installation directory."
    fi
    
    # Load config and update it
    python3 "$INSTALL_DIR/config.py"
    
    # Read database information directly from config.json
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Error: Config file not found at $CONFIG_FILE"
        exit 1
    fi
    
    config=$(cat "$CONFIG_FILE")
    db_container=$(echo $config | jq -r '.db_container')
    db_password=$(echo $config | jq -r '.db_password')
    db_name=$(echo $config | jq -r '.db_name')
    db_type=$(echo $config | jq -r '.db_type')

    # Validate database information
    if [ -z "$db_container" ] || [ -z "$db_password" ] || [ -z "$db_name" ] || [ -z "$db_type" ]; then
        echo "Error: Missing database configuration. Please check your config.json file."
        exit 1
    fi

    # Check if the database container is running
    if ! docker ps | grep -q "$db_container"; then
        echo "Error: Database container $db_container is not running."
        exit 1
    fi

    # Execute SQL script
    echo "Setting up database structures using $db_type..."
    docker exec -i "$db_container" bash -c "$db_type -u root -p'$db_password' $db_name" < "$INSTALL_DIR/hourlyUsage.sql"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to execute SQL script. Please check your database credentials and permissions."
        exit 1
    fi
    
    # Start hourly report script
    echo "Starting hourly report script..."
    nohup python3 "$INSTALL_DIR/hourlyReport.py" > "$LOG_FILE" 2>&1 &
    echo $! > "$USAGE_PID_FILE"
    
    echo "User usage tracking system installed and started."
}

stop_user_usage() {
    echo "Stopping user usage tracking system..."
    if [ -f "$USAGE_PID_FILE" ]; then
        PID=$(cat "$USAGE_PID_FILE")
        if ps -p $PID > /dev/null; then
            kill $PID
            rm "$USAGE_PID_FILE"
            echo "User usage tracking system stopped."
        else
            echo "User usage tracking system is not running, but PID file exists. Removing stale PID file."
            rm "$USAGE_PID_FILE"
        fi
    else
        echo "User usage tracking system is not running."
    fi
}

case "$1" in
    update)
        update $@
        ;;
    start)
        start
        ;;
    stop)
        if [ "$2" == "user-usage" ]; then
            stop_user_usage
        else
            stop
        fi
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
        echo "Usage: marzbackup {update [dev|stable]|start|stop [user-usage]|restart|status|install-user-usage}"
        exit 1
        ;;
esac

exit 0
